#ifndef SLIMED_CUDA_MESH_PACK_HPP
#define SLIMED_CUDA_MESH_PACK_HPP

#include <cstdint>
#include <string>
#include <vector>

class Mesh;

namespace slimed::cuda_residency
{

constexpr std::uint32_t kRegularControlCount = 12;
constexpr std::uint32_t kQuadratureSampleCount = 3;
constexpr std::uint32_t kShapeRowCount = 7;
constexpr std::uint32_t kCoordinateAxisCount = 3;

enum class MeshPackErrorCode
{
    None = 0,
    StaleTopology,
    ArithmeticOverflow,
    InvalidCardinality,
    InvalidIndex,
    DuplicateSourceInFace,
    UnsupportedTopology,
    InvalidNumericalPlan,
    NonFiniteInput,
};

const char *mesh_pack_error_code_name(MeshPackErrorCode code) noexcept;

struct MeshPackError
{
    MeshPackErrorCode code = MeshPackErrorCode::None;
    std::string operation;
    int faceIndex = -1;
    int localControl = -1;
    int sourceId = -1;
    std::string message;

    bool ok() const noexcept
    {
        return code == MeshPackErrorCode::None;
    }
};

struct MeshPackGenerations
{
    std::uint64_t topology = 0;
    std::uint64_t numericalPlan = 0;
    std::uint64_t parameters = 0;
    std::uint64_t acceptedCoordinates = 0;
    std::uint64_t referenceCoordinates = 0;
};

struct RegularMeshPackRequest
{
    MeshPackGenerations generations;
    bool enforceExpectedTopologyGeneration = false;
    std::uint64_t expectedTopologyGeneration = 0;
};

enum class PackedBoundaryMode
{
    Fixed = 0,
    Periodic,
    Free,
};

struct PackedRegularParameters
{
    double kCurv = 0.0;
    double uSurf = 0.0;
    double uVol = 0.0;
    double kReg = 0.0;
    double kSpring = 0.0;
    double area0 = 0.0;
    double area = 0.0;
    double vol0 = 0.0;
    double vol = 0.0;
    double insertCurv = 0.0;
    double spontCurv = 0.0;
    double gamaShape = 0.0;
    double gamaArea = 0.0;
    double elementTriangleArea0 = 0.0;
    bool insertionAreaConstraint = false;
    bool additiveScheme = false;
    bool globalConstraint = false;
    bool usingRpi = false;
    std::int32_t nFaceX = -1;
    std::int32_t nFaceY = -1;
    PackedBoundaryMode boundaryMode = PackedBoundaryMode::Periodic;
};

/**
 * Backend-neutral, owning snapshot of the regular evaluator inputs.
 *
 * Vertex arrays are indexed by declared vertex ID. Face masks are indexed by
 * declared face ID. Evaluated-face arrays use ascending declared face ID and
 * each face's existing local-control order. Shape weights use
 * [sample][row][local-control] order.
 */
struct RegularMeshPack
{
    MeshPackGenerations generations;
    std::uint64_t vertexCount = 0;
    std::uint64_t faceCount = 0;
    std::uint64_t evaluatedFaceCount = 0;

    std::vector<std::uint8_t> vertexBoundaryMask;
    std::vector<std::uint8_t> vertexGhostMask;
    std::vector<std::uint8_t> faceBoundaryMask;
    std::vector<std::uint8_t> faceGhostMask;

    std::vector<std::int32_t> evaluatedFaceIds;
    std::vector<std::int32_t> orientedFaceVertexIds;
    std::vector<std::int32_t> oneRingSourceIds;
    std::vector<std::uint8_t> evaluatedFaceInsertionMask;
    std::vector<double> evaluatedFaceSpontaneousCurvature;

    std::vector<std::uint64_t> sourceOffsets;
    std::vector<std::uint64_t> sourceOccurrences;

    std::vector<double> quadratureSamples;
    std::vector<double> quadratureCoefficients;
    std::vector<double> shapeWeights;

    std::vector<double> acceptedCoordinates;
    std::vector<double> previousCoordinates;
    std::vector<double> referenceCoordinates;
    PackedRegularParameters parameters;
};

struct RegularMeshPackResult
{
    RegularMeshPack pack;
    MeshPackError error;

    bool ok() const noexcept
    {
        return error.ok();
    }
};

RegularMeshPackResult build_regular_mesh_pack(
    const Mesh &mesh,
    const RegularMeshPackRequest &request = RegularMeshPackRequest{});

enum class BackendChoice
{
    Cpu = 0,
    Cuda,
};

enum class EligibilityIssueCode
{
    CudaNotCompiled = 0,
    CudaNotExplicitlySelected,
    DeviceUnavailable,
    DriverRuntimeIncompatible,
    DoublePrecisionUnsupported,
    LaunchLimitsUnsupported,
    MemoryBudgetUnavailable,
    StaleGeneration,
    UnsupportedRegularTopology,
    AlternateEvaluatorUnsupported,
    ScaffoldUnsupported,
    GagUnsupported,
    IdealizedLatticeUnsupported,
    ThermalUnsupported,
    DynamicMeshUnsupported,
    InsertionUnsupported,
    BoundaryModeUnsupported,
    PriorCudaError,
    InvalidPackedInput,
};

const char *eligibility_issue_code_name(EligibilityIssueCode code) noexcept;

struct EligibilityIssue
{
    EligibilityIssueCode code = EligibilityIssueCode::InvalidPackedInput;
    std::string operation;
    std::string message;
};

struct CudaEligibilityRequest
{
    BackendChoice backend = BackendChoice::Cpu;
    RegularMeshPackRequest packRequest;

    bool cudaExplicitlySelected = false;
    bool cudaCompiledByExplicitOptIn = false;
    bool deviceAvailable = false;
    bool driverRuntimeCompatible = false;
    bool doublePrecisionSupported = false;
    bool launchLimitsSupported = false;
    bool memoryBudgetAvailable = false;
    bool alternateEvaluatorRequested = false;
    bool dynamicMeshEnabled = false;
    bool fixedBoundaryProven = false;
    bool periodicBoundaryProven = false;
    bool freeBoundaryProven = false;
    bool priorUnrecoveredCudaError = false;
};

struct CudaEligibilityResult
{
    BackendChoice backend = BackendChoice::Cpu;
    bool eligible = true;
    std::vector<EligibilityIssue> issues;
    RegularMeshPackResult packedInput;
};

CudaEligibilityResult evaluate_cuda_eligibility(
    const Mesh &mesh,
    const CudaEligibilityRequest &request);

} // namespace slimed::cuda_residency

#endif
