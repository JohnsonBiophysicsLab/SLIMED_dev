#include "cuda/Cuda_mesh_pack.hpp"

#include "cuda/detail/Cuda_checked_arithmetic.hpp"
#include "mesh/Mesh.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <sstream>
#include <utility>

namespace slimed::cuda_residency
{
namespace
{

MeshPackError make_pack_error(const MeshPackErrorCode code,
                              const char *operation,
                              const std::string &message,
                              const int faceIndex = -1,
                              const int localControl = -1,
                              const int sourceId = -1)
{
    MeshPackError error;
    error.code = code;
    error.operation = operation;
    error.faceIndex = faceIndex;
    error.localControl = localControl;
    error.sourceId = sourceId;
    error.message = message;
    return error;
}

RegularMeshPackResult pack_failure(const MeshPackError &error)
{
    RegularMeshPackResult result;
    result.error = error;
    return result;
}

bool finite_matrix(const Matrix &matrix)
{
    if (matrix.mat == nullptr)
    {
        return false;
    }
    for (int row = 0; row < matrix.nrow(); ++row)
    {
        for (int column = 0; column < matrix.ncol(); ++column)
        {
            if (!std::isfinite(matrix.get(row, column)))
            {
                return false;
            }
        }
    }
    return true;
}

bool finite_values(const PackedRegularParameters &parameters)
{
    return std::isfinite(parameters.kCurv) &&
           std::isfinite(parameters.uSurf) &&
           std::isfinite(parameters.uVol) &&
           std::isfinite(parameters.kReg) &&
           std::isfinite(parameters.kSpring) &&
           std::isfinite(parameters.area0) &&
           std::isfinite(parameters.area) &&
           std::isfinite(parameters.vol0) &&
           std::isfinite(parameters.vol) &&
           std::isfinite(parameters.insertCurv) &&
           std::isfinite(parameters.spontCurv) &&
           std::isfinite(parameters.gamaShape) &&
           std::isfinite(parameters.gamaArea) &&
           std::isfinite(parameters.elementTriangleArea0);
}

PackedBoundaryMode packed_boundary_mode(const BoundaryType mode)
{
    switch (mode)
    {
    case BoundaryType::Fixed:
        return PackedBoundaryMode::Fixed;
    case BoundaryType::Periodic:
        return PackedBoundaryMode::Periodic;
    case BoundaryType::Free:
        return PackedBoundaryMode::Free;
    }
    return PackedBoundaryMode::Periodic;
}

void add_issue(CudaEligibilityResult &result,
               const EligibilityIssueCode code,
               const char *operation,
               const std::string &message)
{
    result.issues.push_back(EligibilityIssue{code, operation, message});
}

bool boundary_is_proven(const BoundaryType mode,
                        const CudaEligibilityRequest &request)
{
    switch (mode)
    {
    case BoundaryType::Fixed:
        return request.fixedBoundaryProven;
    case BoundaryType::Periodic:
        return request.periodicBoundaryProven;
    case BoundaryType::Free:
        return request.freeBoundaryProven;
    }
    return false;
}

} // namespace

const char *mesh_pack_error_code_name(const MeshPackErrorCode code) noexcept
{
    switch (code)
    {
    case MeshPackErrorCode::None:
        return "none";
    case MeshPackErrorCode::StaleTopology:
        return "stale_topology";
    case MeshPackErrorCode::ArithmeticOverflow:
        return "arithmetic_overflow";
    case MeshPackErrorCode::InvalidCardinality:
        return "invalid_cardinality";
    case MeshPackErrorCode::InvalidIndex:
        return "invalid_index";
    case MeshPackErrorCode::DuplicateSourceInFace:
        return "duplicate_source_in_face";
    case MeshPackErrorCode::UnsupportedTopology:
        return "unsupported_topology";
    case MeshPackErrorCode::InvalidNumericalPlan:
        return "invalid_numerical_plan";
    case MeshPackErrorCode::NonFiniteInput:
        return "nonfinite_input";
    }
    return "unknown";
}

const char *eligibility_issue_code_name(const EligibilityIssueCode code) noexcept
{
    switch (code)
    {
    case EligibilityIssueCode::CudaNotCompiled:
        return "cuda_not_compiled";
    case EligibilityIssueCode::CudaNotExplicitlySelected:
        return "cuda_not_explicitly_selected";
    case EligibilityIssueCode::DeviceUnavailable:
        return "device_unavailable";
    case EligibilityIssueCode::DriverRuntimeIncompatible:
        return "driver_runtime_incompatible";
    case EligibilityIssueCode::DoublePrecisionUnsupported:
        return "double_precision_unsupported";
    case EligibilityIssueCode::LaunchLimitsUnsupported:
        return "launch_limits_unsupported";
    case EligibilityIssueCode::MemoryBudgetUnavailable:
        return "memory_budget_unavailable";
    case EligibilityIssueCode::StaleGeneration:
        return "stale_generation";
    case EligibilityIssueCode::UnsupportedRegularTopology:
        return "unsupported_regular_topology";
    case EligibilityIssueCode::AlternateEvaluatorUnsupported:
        return "alternate_evaluator_unsupported";
    case EligibilityIssueCode::ScaffoldUnsupported:
        return "scaffold_unsupported";
    case EligibilityIssueCode::GagUnsupported:
        return "gag_unsupported";
    case EligibilityIssueCode::IdealizedLatticeUnsupported:
        return "idealized_lattice_unsupported";
    case EligibilityIssueCode::ThermalUnsupported:
        return "thermal_unsupported";
    case EligibilityIssueCode::DynamicMeshUnsupported:
        return "dynamic_mesh_unsupported";
    case EligibilityIssueCode::InsertionUnsupported:
        return "insertion_unsupported";
    case EligibilityIssueCode::BoundaryModeUnsupported:
        return "boundary_mode_unsupported";
    case EligibilityIssueCode::PriorCudaError:
        return "prior_cuda_error";
    case EligibilityIssueCode::InvalidPackedInput:
        return "invalid_packed_input";
    }
    return "unknown";
}

RegularMeshPackResult build_regular_mesh_pack(
    const Mesh &mesh,
    const RegularMeshPackRequest &request)
{
    if (request.enforceExpectedTopologyGeneration &&
        request.generations.topology != request.expectedTopologyGeneration)
    {
        std::ostringstream message;
        message << "topology generation " << request.generations.topology
                << " does not match expected generation "
                << request.expectedTopologyGeneration;
        return pack_failure(make_pack_error(MeshPackErrorCode::StaleTopology,
                                            "mesh_pack.topology_generation",
                                            message.str()));
    }

    const std::uint64_t vertexCount = mesh.vertices.size();
    const std::uint64_t faceCount = mesh.faces.size();
    if (vertexCount == 0 || faceCount == 0)
    {
        return pack_failure(make_pack_error(
            MeshPackErrorCode::InvalidCardinality,
            "mesh_pack.mesh_cardinality",
            "a regular CUDA input requires at least one vertex and one face"));
    }
    if (vertexCount > static_cast<std::uint64_t>(
                          std::numeric_limits<std::int32_t>::max()) ||
        faceCount > static_cast<std::uint64_t>(
                        std::numeric_limits<std::int32_t>::max()))
    {
        return pack_failure(make_pack_error(
            MeshPackErrorCode::ArithmeticOverflow,
            "mesh_pack.identity_tables",
            "vertex or face cardinality exceeds the packed 32-bit identity range"));
    }

    std::vector<const Vertex *> verticesById(
        static_cast<std::size_t>(vertexCount), nullptr);
    for (const Vertex &vertex : mesh.vertices)
    {
        if (vertex.index < 0 ||
            static_cast<std::uint64_t>(vertex.index) >= vertexCount)
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::InvalidIndex,
                "mesh_pack.vertex_identity",
                "vertex IDs must be a contiguous zero-based permutation",
                -1,
                -1,
                vertex.index));
        }
        const std::size_t id = static_cast<std::size_t>(vertex.index);
        if (verticesById[id] != nullptr)
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::InvalidIndex,
                "mesh_pack.vertex_identity",
                "duplicate declared vertex ID",
                -1,
                -1,
                vertex.index));
        }
        verticesById[id] = &vertex;
    }

    std::vector<const Face *> facesById(static_cast<std::size_t>(faceCount),
                                        nullptr);
    for (const Face &face : mesh.faces)
    {
        if (face.index < 0 ||
            static_cast<std::uint64_t>(face.index) >= faceCount)
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::InvalidIndex,
                "mesh_pack.face_identity",
                "face IDs must be a contiguous zero-based permutation",
                face.index));
        }
        const std::size_t id = static_cast<std::size_t>(face.index);
        if (facesById[id] != nullptr)
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::InvalidIndex,
                "mesh_pack.face_identity",
                "duplicate declared face ID",
                face.index));
        }
        facesById[id] = &face;
    }

    std::vector<const Face *> evaluatedFaces;
    evaluatedFaces.reserve(facesById.size());
    for (const Face *face : facesById)
    {
        if (!face->isGhost)
        {
            evaluatedFaces.push_back(face);
        }
    }
    if (evaluatedFaces.empty())
    {
        return pack_failure(make_pack_error(
            MeshPackErrorCode::InvalidCardinality,
            "mesh_pack.evaluated_face_cardinality",
            "a regular CUDA input requires at least one non-ghost face"));
    }

    std::uint64_t occurrenceCount = 0;
    if (!detail::checked_multiply(evaluatedFaces.size(),
                                  kRegularControlCount,
                                  occurrenceCount) ||
        occurrenceCount > static_cast<std::uint64_t>(
                              std::numeric_limits<std::size_t>::max()))
    {
        return pack_failure(make_pack_error(
            MeshPackErrorCode::ArithmeticOverflow,
            "mesh_pack.occurrence_cardinality",
            "regular face occurrence cardinality overflow"));
    }

    std::uint64_t coordinateCount = 0;
    if (!detail::checked_multiply(vertexCount,
                                  kCoordinateAxisCount,
                                  coordinateCount) ||
        coordinateCount > static_cast<std::uint64_t>(
                              std::numeric_limits<std::size_t>::max()))
    {
        return pack_failure(make_pack_error(
            MeshPackErrorCode::ArithmeticOverflow,
            "mesh_pack.coordinate_cardinality",
            "coordinate cardinality overflow"));
    }

    RegularMeshPack pack;
    pack.generations = request.generations;
    pack.vertexCount = vertexCount;
    pack.faceCount = faceCount;
    pack.evaluatedFaceCount = evaluatedFaces.size();
    pack.vertexBoundaryMask.resize(static_cast<std::size_t>(vertexCount));
    pack.vertexGhostMask.resize(static_cast<std::size_t>(vertexCount));
    pack.faceBoundaryMask.resize(static_cast<std::size_t>(faceCount));
    pack.faceGhostMask.resize(static_cast<std::size_t>(faceCount));
    pack.acceptedCoordinates.reserve(static_cast<std::size_t>(coordinateCount));
    pack.previousCoordinates.reserve(static_cast<std::size_t>(coordinateCount));
    pack.referenceCoordinates.reserve(static_cast<std::size_t>(coordinateCount));

    for (std::size_t id = 0; id < verticesById.size(); ++id)
    {
        const Vertex &vertex = *verticesById[id];
        if (vertex.coord.mat == nullptr || vertex.coord.nrow() != 3 ||
            vertex.coord.ncol() != 1 || vertex.coordPrev.mat == nullptr ||
            vertex.coordPrev.nrow() != 3 || vertex.coordPrev.ncol() != 1 ||
            vertex.coordRef.mat == nullptr || vertex.coordRef.nrow() != 3 ||
            vertex.coordRef.ncol() != 1)
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::InvalidCardinality,
                "mesh_pack.vertex_coordinates",
                "accepted, previous, and reference coordinates must each be 3x1",
                -1,
                -1,
                static_cast<int>(id)));
        }
        if (!finite_matrix(vertex.coord) || !finite_matrix(vertex.coordPrev) ||
            !finite_matrix(vertex.coordRef))
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::NonFiniteInput,
                "mesh_pack.vertex_coordinates",
                "accepted, previous, and reference coordinates must be finite",
                -1,
                -1,
                static_cast<int>(id)));
        }
        pack.vertexBoundaryMask[id] = vertex.isBoundary ? 1U : 0U;
        pack.vertexGhostMask[id] = vertex.isGhost ? 1U : 0U;
        for (int axis = 0; axis < 3; ++axis)
        {
            pack.acceptedCoordinates.push_back(vertex.coord.get(axis, 0));
            pack.previousCoordinates.push_back(vertex.coordPrev.get(axis, 0));
            pack.referenceCoordinates.push_back(vertex.coordRef.get(axis, 0));
        }
    }

    for (std::size_t id = 0; id < facesById.size(); ++id)
    {
        pack.faceBoundaryMask[id] = facesById[id]->isBoundary ? 1U : 0U;
        pack.faceGhostMask[id] = facesById[id]->isGhost ? 1U : 0U;
    }

    pack.evaluatedFaceIds.reserve(evaluatedFaces.size());
    pack.orientedFaceVertexIds.reserve(evaluatedFaces.size() * 3U);
    pack.oneRingSourceIds.reserve(static_cast<std::size_t>(occurrenceCount));
    pack.evaluatedFaceInsertionMask.reserve(evaluatedFaces.size());
    pack.evaluatedFaceSpontaneousCurvature.reserve(evaluatedFaces.size());
    std::vector<std::uint64_t> sourceCounts(static_cast<std::size_t>(vertexCount),
                                            0);

    for (const Face *face : evaluatedFaces)
    {
        if (face->adjacentVertices.size() != 3U)
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::InvalidCardinality,
                "mesh_pack.oriented_face",
                "evaluated triangular faces must have exactly three oriented vertices",
                face->index));
        }
        if (face->oneRingVertices.size() != kRegularControlCount)
        {
            std::ostringstream message;
            message << "evaluated face requires exactly " << kRegularControlCount
                    << " controls; found " << face->oneRingVertices.size();
            return pack_failure(make_pack_error(
                MeshPackErrorCode::UnsupportedTopology,
                "mesh_pack.regular_topology",
                message.str(),
                face->index));
        }
        if (!std::isfinite(face->spontCurvature))
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::NonFiniteInput,
                "mesh_pack.face_parameters",
                "face spontaneous curvature must be finite",
                face->index));
        }

        for (const int vertexId : face->adjacentVertices)
        {
            if (vertexId < 0 ||
                static_cast<std::uint64_t>(vertexId) >= vertexCount)
            {
                return pack_failure(make_pack_error(
                    MeshPackErrorCode::InvalidIndex,
                    "mesh_pack.oriented_face",
                    "oriented face vertex ID is outside the packed vertex range",
                    face->index,
                    -1,
                    vertexId));
            }
        }
        if (face->adjacentVertices[0] == face->adjacentVertices[1] ||
            face->adjacentVertices[0] == face->adjacentVertices[2] ||
            face->adjacentVertices[1] == face->adjacentVertices[2])
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::InvalidIndex,
                "mesh_pack.oriented_face",
                "an evaluated triangular face requires three distinct vertex IDs",
                face->index));
        }

        pack.evaluatedFaceIds.push_back(face->index);
        for (const int vertexId : face->adjacentVertices)
        {
            pack.orientedFaceVertexIds.push_back(vertexId);
        }
        pack.evaluatedFaceInsertionMask.push_back(
            face->isInsertionPatch ? 1U : 0U);
        pack.evaluatedFaceSpontaneousCurvature.push_back(face->spontCurvature);

        for (std::size_t local = 0; local < face->oneRingVertices.size(); ++local)
        {
            const int sourceId = face->oneRingVertices[local];
            if (sourceId < 0 ||
                static_cast<std::uint64_t>(sourceId) >= vertexCount)
            {
                return pack_failure(make_pack_error(
                    MeshPackErrorCode::InvalidIndex,
                    "mesh_pack.one_ring",
                    "one-ring source ID is outside the packed vertex range",
                    face->index,
                    static_cast<int>(local),
                    sourceId));
            }
            if (std::find(face->oneRingVertices.begin(),
                          face->oneRingVertices.begin() +
                              static_cast<std::ptrdiff_t>(local),
                          sourceId) !=
                face->oneRingVertices.begin() +
                    static_cast<std::ptrdiff_t>(local))
            {
                return pack_failure(make_pack_error(
                    MeshPackErrorCode::DuplicateSourceInFace,
                    "mesh_pack.one_ring",
                    "a regular face cannot contain the same source ID twice",
                    face->index,
                    static_cast<int>(local),
                    sourceId));
            }
            std::uint64_t nextCount = 0;
            if (!detail::checked_add(
                    sourceCounts[static_cast<std::size_t>(sourceId)],
                    1,
                    nextCount))
            {
                return pack_failure(make_pack_error(
                    MeshPackErrorCode::ArithmeticOverflow,
                    "mesh_pack.incidence_count",
                    "source incidence count overflow",
                    face->index,
                    static_cast<int>(local),
                    sourceId));
            }
            sourceCounts[static_cast<std::size_t>(sourceId)] = nextCount;
            pack.oneRingSourceIds.push_back(sourceId);
        }
        for (const int vertexId : face->adjacentVertices)
        {
            if (std::count(face->oneRingVertices.begin(),
                           face->oneRingVertices.end(),
                           vertexId) != 1)
            {
                return pack_failure(make_pack_error(
                    MeshPackErrorCode::InvalidIndex,
                    "mesh_pack.oriented_face_membership",
                    "each oriented face vertex must occur exactly once in its one-ring",
                    face->index,
                    -1,
                    vertexId));
            }
        }
    }

    pack.sourceOffsets.resize(static_cast<std::size_t>(vertexCount + 1U), 0);
    for (std::size_t source = 0; source < sourceCounts.size(); ++source)
    {
        if (!detail::checked_add(pack.sourceOffsets[source],
                                 sourceCounts[source],
                                 pack.sourceOffsets[source + 1U]))
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::ArithmeticOverflow,
                "mesh_pack.incidence_scan",
                "source incidence exclusive scan overflow",
                -1,
                -1,
                static_cast<int>(source)));
        }
    }
    if (pack.sourceOffsets.back() != occurrenceCount)
    {
        return pack_failure(make_pack_error(
            MeshPackErrorCode::InvalidCardinality,
            "mesh_pack.incidence_scan",
            "source incidence scan does not end at occurrence cardinality"));
    }

    pack.sourceOccurrences.resize(static_cast<std::size_t>(occurrenceCount));
    std::vector<std::uint64_t> cursors = pack.sourceOffsets;
    for (std::uint64_t occurrence = 0; occurrence < occurrenceCount; ++occurrence)
    {
        const int sourceId =
            pack.oneRingSourceIds[static_cast<std::size_t>(occurrence)];
        const std::size_t source = static_cast<std::size_t>(sourceId);
        const std::uint64_t destination = cursors[source]++;
        if (destination >= pack.sourceOffsets[source + 1U])
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::InvalidCardinality,
                "mesh_pack.incidence_fill",
                "source incidence fill exceeded its scanned range",
                -1,
                -1,
                sourceId));
        }
        pack.sourceOccurrences[static_cast<std::size_t>(destination)] = occurrence;
    }

    std::vector<std::uint8_t> seen(static_cast<std::size_t>(occurrenceCount), 0);
    for (std::size_t source = 0; source < sourceCounts.size(); ++source)
    {
        if (pack.sourceOffsets[source] > pack.sourceOffsets[source + 1U])
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::InvalidCardinality,
                "mesh_pack.incidence_validate",
                "source offsets must be monotonic"));
        }
        for (std::uint64_t cursor = pack.sourceOffsets[source];
             cursor < pack.sourceOffsets[source + 1U];
             ++cursor)
        {
            const std::uint64_t occurrence =
                pack.sourceOccurrences[static_cast<std::size_t>(cursor)];
            if (occurrence >= occurrenceCount ||
                pack.oneRingSourceIds[static_cast<std::size_t>(occurrence)] !=
                    static_cast<int>(source) ||
                seen[static_cast<std::size_t>(occurrence)] != 0U)
            {
                return pack_failure(make_pack_error(
                    MeshPackErrorCode::InvalidCardinality,
                    "mesh_pack.incidence_validate",
                    "incidence plan must contain every canonical occurrence exactly once"));
            }
            seen[static_cast<std::size_t>(occurrence)] = 1U;
        }
    }
    if (std::find(seen.begin(), seen.end(), 0U) != seen.end())
    {
        return pack_failure(make_pack_error(
            MeshPackErrorCode::InvalidCardinality,
            "mesh_pack.incidence_validate",
            "incidence plan omitted a canonical occurrence"));
    }

    const Param &parameters = mesh.param;
    if (parameters.gaussQuadratureN != 2 || parameters.VWU.mat == nullptr ||
        parameters.VWU.nrow() != static_cast<int>(kQuadratureSampleCount) ||
        parameters.VWU.ncol() != 3 ||
        parameters.gaussQuadratureCoeff.mat == nullptr ||
        parameters.gaussQuadratureCoeff.nrow() !=
            static_cast<int>(kQuadratureSampleCount) ||
        parameters.gaussQuadratureCoeff.ncol() != 1 ||
        parameters.shapeFunctions.size() != kQuadratureSampleCount)
    {
        return pack_failure(make_pack_error(
            MeshPackErrorCode::InvalidNumericalPlan,
            "mesh_pack.numerical_plan",
            "regular CUDA input requires the 3-sample order-2 quadrature plan"));
    }
    if (!finite_matrix(parameters.VWU) ||
        !finite_matrix(parameters.gaussQuadratureCoeff))
    {
        return pack_failure(make_pack_error(
            MeshPackErrorCode::NonFiniteInput,
            "mesh_pack.numerical_plan",
            "quadrature samples and coefficients must be finite"));
    }

    pack.quadratureSamples.reserve(kQuadratureSampleCount * 3U);
    pack.quadratureCoefficients.reserve(kQuadratureSampleCount);
    pack.shapeWeights.reserve(kQuadratureSampleCount * kShapeRowCount *
                              kRegularControlCount);
    for (std::uint32_t sample = 0; sample < kQuadratureSampleCount; ++sample)
    {
        for (int column = 0; column < 3; ++column)
        {
            pack.quadratureSamples.push_back(
                parameters.VWU.get(static_cast<int>(sample), column));
        }
        pack.quadratureCoefficients.push_back(
            parameters.gaussQuadratureCoeff.get(static_cast<int>(sample), 0));
        const Matrix &shape = parameters.shapeFunctions[sample];
        if (shape.mat == nullptr ||
            shape.nrow() != static_cast<int>(kShapeRowCount) ||
            shape.ncol() != static_cast<int>(kRegularControlCount))
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::InvalidNumericalPlan,
                "mesh_pack.shape_rows",
                "each regular shape-function sample must be a 7x12 matrix"));
        }
        if (!finite_matrix(shape))
        {
            return pack_failure(make_pack_error(
                MeshPackErrorCode::NonFiniteInput,
                "mesh_pack.shape_rows",
                "shape-function rows must be finite"));
        }
        for (std::uint32_t row = 0; row < kShapeRowCount; ++row)
        {
            for (std::uint32_t local = 0; local < kRegularControlCount; ++local)
            {
                pack.shapeWeights.push_back(shape.get(
                    static_cast<int>(row), static_cast<int>(local)));
            }
        }
    }

    pack.parameters.kCurv = parameters.kCurv;
    pack.parameters.uSurf = parameters.uSurf;
    pack.parameters.uVol = parameters.uVol;
    pack.parameters.kReg = parameters.kReg;
    pack.parameters.kSpring = parameters.kSpring;
    pack.parameters.area0 = parameters.area0;
    pack.parameters.area = parameters.area;
    pack.parameters.vol0 = parameters.vol0;
    pack.parameters.vol = parameters.vol;
    pack.parameters.insertCurv = parameters.insertCurv;
    pack.parameters.spontCurv = parameters.spontCurv;
    pack.parameters.gamaShape = parameters.gamaShape;
    pack.parameters.gamaArea = parameters.gamaArea;
    pack.parameters.elementTriangleArea0 = parameters.elementTriangleArea0;
    pack.parameters.insertionAreaConstraint =
        parameters.isInsertionAreaConstraint;
    pack.parameters.additiveScheme = parameters.isAdditiveScheme;
    pack.parameters.globalConstraint = parameters.isGlobalConstraint;
    pack.parameters.usingRpi = parameters.usingRpi;
    pack.parameters.nFaceX = parameters.nFaceX;
    pack.parameters.nFaceY = parameters.nFaceY;
    pack.parameters.boundaryMode =
        packed_boundary_mode(parameters.boundaryCondition);
    if (!finite_values(pack.parameters))
    {
        return pack_failure(make_pack_error(
            MeshPackErrorCode::NonFiniteInput,
            "mesh_pack.parameters",
            "packed regular physical parameters must be finite"));
    }

    RegularMeshPackResult result;
    result.pack = std::move(pack);
    return result;
}

CudaEligibilityResult evaluate_cuda_eligibility(
    const Mesh &mesh,
    const CudaEligibilityRequest &request)
{
    CudaEligibilityResult result;
    result.backend = request.backend;
    if (request.backend == BackendChoice::Cpu)
    {
        result.eligible = true;
        return result;
    }

    if (!request.cudaExplicitlySelected)
    {
        add_issue(result,
                  EligibilityIssueCode::CudaNotExplicitlySelected,
                  "cuda_preflight.selection",
                  "CUDA requires an explicit user backend selection");
    }
    if (!request.cudaCompiledByExplicitOptIn)
    {
        add_issue(result,
                  EligibilityIssueCode::CudaNotCompiled,
                  "cuda_preflight.compilation",
                  "CUDA backend was not compiled by an explicit opt-in target");
    }
    if (!request.deviceAvailable)
    {
        add_issue(result,
                  EligibilityIssueCode::DeviceUnavailable,
                  "cuda_preflight.device",
                  "no compatible CUDA device is available");
    }
    if (!request.driverRuntimeCompatible)
    {
        add_issue(result,
                  EligibilityIssueCode::DriverRuntimeIncompatible,
                  "cuda_preflight.driver_runtime",
                  "CUDA driver and runtime compatibility was not established");
    }
    if (!request.doublePrecisionSupported)
    {
        add_issue(result,
                  EligibilityIssueCode::DoublePrecisionUnsupported,
                  "cuda_preflight.double_precision",
                  "required double-precision capability was not established");
    }
    if (!request.launchLimitsSupported)
    {
        add_issue(result,
                  EligibilityIssueCode::LaunchLimitsUnsupported,
                  "cuda_preflight.launch_limits",
                  "required CUDA grid and block limits were not established");
    }
    if (!request.memoryBudgetAvailable)
    {
        add_issue(result,
                  EligibilityIssueCode::MemoryBudgetUnavailable,
                  "cuda_preflight.memory_budget",
                  "required device memory budget is unavailable");
    }

    result.packedInput = build_regular_mesh_pack(mesh, request.packRequest);
    if (!result.packedInput.ok())
    {
        const MeshPackError &error = result.packedInput.error;
        EligibilityIssueCode issueCode =
            EligibilityIssueCode::InvalidPackedInput;
        if (error.code == MeshPackErrorCode::StaleTopology)
        {
            issueCode = EligibilityIssueCode::StaleGeneration;
        }
        else if (error.code == MeshPackErrorCode::UnsupportedTopology)
        {
            issueCode = EligibilityIssueCode::UnsupportedRegularTopology;
        }
        add_issue(result,
                  issueCode,
                  "cuda_preflight.packed_input",
                  std::string(mesh_pack_error_code_name(error.code)) + ": " +
                      error.message);
    }
    if (request.alternateEvaluatorRequested)
    {
        add_issue(result,
                  EligibilityIssueCode::AlternateEvaluatorUnsupported,
                  "cuda_preflight.alternate_evaluator",
                  "alternate regular evaluation is outside the initial CUDA route");
    }

    const Param &parameters = mesh.param;
    if (parameters.isEnergyHarmonicBondIncluded)
    {
        add_issue(result,
                  EligibilityIssueCode::ScaffoldUnsupported,
                  "cuda_preflight.scaffold",
                  "scaffolding harmonic-bond energy is outside the initial CUDA route");
    }
    if (parameters.isGagScaffoldingEnergyIncluded)
    {
        add_issue(result,
                  EligibilityIssueCode::GagUnsupported,
                  "cuda_preflight.gag",
                  "Gag scaffolding energy is outside the initial CUDA route");
    }
    if (parameters.isIdealizedProteinLatticeEnergyIncluded)
    {
        add_issue(result,
                  EligibilityIssueCode::IdealizedLatticeUnsupported,
                  "cuda_preflight.idealized_lattice",
                  "idealized protein lattice energy is outside the initial CUDA route");
    }
    if (parameters.thermalFluctuationEnabled ||
        parameters.thermalFluctuationPureMMC)
    {
        add_issue(result,
                  EligibilityIssueCode::ThermalUnsupported,
                  "cuda_preflight.thermal",
                  "thermal and Metropolis moves are outside the initial CUDA route");
    }
    if (request.dynamicMeshEnabled)
    {
        add_issue(result,
                  EligibilityIssueCode::DynamicMeshUnsupported,
                  "cuda_preflight.dynamic_mesh",
                  "dynamic-mesh workflows are outside the initial CUDA route");
    }

    const bool faceInsertion = std::any_of(
        mesh.faces.begin(), mesh.faces.end(), [](const Face &face) {
            return !face.isGhost && face.isInsertionPatch;
        });
    if (parameters.isInsertionIncluded ||
        parameters.isInsertionAreaConstraint ||
        !parameters.insertionPatch.empty() || faceInsertion)
    {
        add_issue(result,
                  EligibilityIssueCode::InsertionUnsupported,
                  "cuda_preflight.insertion",
                  "insertion semantics have not yet been proven for the CUDA route");
    }
    if (!boundary_is_proven(parameters.boundaryCondition, request))
    {
        add_issue(result,
                  EligibilityIssueCode::BoundaryModeUnsupported,
                  "cuda_preflight.boundary",
                  "the selected boundary mode has not been proven for the CUDA route");
    }
    if (request.priorUnrecoveredCudaError)
    {
        add_issue(result,
                  EligibilityIssueCode::PriorCudaError,
                  "cuda_preflight.prior_error",
                  "a prior unrecovered CUDA error invalidates this state");
    }

    result.eligible = result.issues.empty();
    return result;
}

} // namespace slimed::cuda_residency
