#include "energy_force/Source_keyed_kernel_call.hpp"

#include "mesh/Mesh.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>

namespace slimed::source_keyed_kernel
{
namespace
{
void require_unique_source_ids(const std::vector<int> &sourceIds,
                               const int sourceCount,
                               const std::string &context)
{
    std::unordered_set<int> seen;
    for (const int sourceId : sourceIds)
    {
        if (sourceId < 0 || sourceId >= sourceCount)
        {
            throw std::invalid_argument(
                context + " contains an out-of-range original source id");
        }
        if (!seen.insert(sourceId).second)
        {
            throw std::invalid_argument(
                context + " contains a duplicate original source id");
        }
    }
}

std::vector<int> canonical_source_ids(const std::vector<int> &sourceIds,
                                      const int sourceCount,
                                      const std::string &context)
{
    if (sourceIds.empty())
    {
        throw std::invalid_argument(
            context + " requires at least one original source id");
    }
    require_unique_source_ids(sourceIds, sourceCount, context);
    std::vector<int> canonical = sourceIds;
    std::sort(canonical.begin(), canonical.end());
    return canonical;
}

SourceKeyedRow canonicalize_derivative_row(
    const SourceKeyedRow &row,
    const std::vector<int> &canonicalSourceIds,
    const int sourceCount)
{
    if (row.sourceIds.empty() ||
        row.sourceIds.size() != row.coefficients.size())
    {
        throw std::invalid_argument(
            "source-keyed kernel helper rejected row mapping/cardinality "
            "drift");
    }

    std::vector<std::vector<double>> contributions(sourceCount);
    for (std::size_t position = 0; position < row.sourceIds.size(); ++position)
    {
        const int sourceId = row.sourceIds[position];
        const double coefficient = row.coefficients[position];
        if (sourceId < 0 || sourceId >= sourceCount ||
            !std::binary_search(canonicalSourceIds.begin(),
                                canonicalSourceIds.end(),
                                sourceId))
        {
            throw std::invalid_argument(
                "derivative row contains an out-of-range or unmapped "
                "original source id");
        }
        if (!std::isfinite(coefficient))
        {
            throw std::invalid_argument(
                "source-keyed kernel helper rejected nonfinite row data");
        }
        contributions[sourceId].push_back(coefficient);
    }

    SourceKeyedRow canonical;
    canonical.sourceIds = canonicalSourceIds;
    canonical.coefficients.reserve(canonicalSourceIds.size());
    for (const int sourceId : canonicalSourceIds)
    {
        std::vector<double> &values = contributions[sourceId];
        if (values.empty())
        {
            throw std::invalid_argument(
                "source-keyed kernel helper rejected incomplete row source "
                "coverage");
        }
        std::sort(values.begin(), values.end());
        long double sum = 0.0L;
        for (const double value : values)
        {
            sum += static_cast<long double>(value);
        }
        canonical.coefficients.push_back(static_cast<double>(sum));
    }
    return canonical;
}

std::vector<SourceForceKinds> canonicalize_forces(
    const SourceKeyedFaceForces &faceForces,
    const std::vector<int> &canonicalSourceIds,
    const int sourceCount)
{
    if (faceForces.sourceIds.size() != faceForces.forces.size())
    {
        throw std::invalid_argument(
            "source-keyed kernel helper rejected force mapping/cardinality "
            "drift");
    }
    require_unique_source_ids(faceForces.sourceIds,
                              sourceCount,
                              "force input");

    std::vector<SourceForceKinds> bySource(sourceCount);
    std::vector<bool> present(sourceCount, false);
    for (std::size_t position = 0; position < faceForces.sourceIds.size();
         ++position)
    {
        const int sourceId = faceForces.sourceIds[position];
        if (!std::binary_search(canonicalSourceIds.begin(),
                                canonicalSourceIds.end(),
                                sourceId))
        {
            throw std::invalid_argument(
                "source-keyed kernel helper rejected force source mapping "
                "drift");
        }
        const SourceForceKinds &sourceForces = faceForces.forces[position];
        for (const Vec3 &force : sourceForces)
        {
            if (!std::all_of(force.begin(), force.end(), [](double value) {
                    return std::isfinite(value);
                }))
            {
                throw std::invalid_argument(
                    "source-keyed kernel helper rejected nonfinite force "
                    "data");
            }
        }
        bySource[sourceId] = sourceForces;
        present[sourceId] = true;
    }

    std::vector<SourceForceKinds> canonical;
    canonical.reserve(canonicalSourceIds.size());
    for (const int sourceId : canonicalSourceIds)
    {
        if (!present[sourceId])
        {
            throw std::invalid_argument(
                "source-keyed kernel helper rejected incomplete force source "
                "coverage");
        }
        canonical.push_back(bySource[sourceId]);
    }
    if (canonical.size() != faceForces.forces.size())
    {
        throw std::invalid_argument(
            "source-keyed kernel helper rejected force mapping/cardinality "
            "drift");
    }
    return canonical;
}
} // namespace

PreparedSourceKeyedKernelCall prepare_source_keyed_kernel_call(
    const SourceKeyedKernelCallInput &input)
{
    if (input.sourceCount <= 0 || input.mappings.empty() ||
        input.mappings.size() != input.rows.size() ||
        input.mappings.size() != input.forces.size())
    {
        throw std::invalid_argument(
            "source-keyed kernel helper requires matching nonempty face "
            "collections");
    }

    PreparedSourceKeyedKernelCall prepared;
    prepared.sourceCount = input.sourceCount;
    prepared.faces.reserve(input.mappings.size());
    for (std::size_t facePosition = 0;
         facePosition < input.mappings.size();
         ++facePosition)
    {
        const SourceMappingView &mapping = input.mappings[facePosition];
        const SourceKeyedFaceRows &faceRows = input.rows[facePosition];
        const SourceKeyedFaceForces &faceForces =
            input.forces[facePosition];
        if (mapping.faceIndex != static_cast<int>(facePosition) ||
            faceRows.faceIndex != mapping.faceIndex ||
            faceForces.faceIndex != mapping.faceIndex)
        {
            throw std::invalid_argument(
                "source-keyed kernel helper requires stable face identity");
        }
        if (!mapping.productionOneRingEmpty)
        {
            throw std::invalid_argument(
                "source-keyed kernel helper requires empty production "
                "one-rings");
        }
        if (faceRows.orientedFaceVertices !=
            mapping.orientedFaceVertices)
        {
            throw std::invalid_argument(
                "source-keyed kernel helper rejected face orientation drift");
        }
        const std::vector<int> canonicalSourceIds =
            canonical_source_ids(mapping.originalSourceIds,
                                 input.sourceCount,
                                 "source mapping");
        const std::vector<SourceForceKinds> canonicalForces =
            canonicalize_forces(faceForces,
                                canonicalSourceIds,
                                input.sourceCount);
        if (faceRows.samples.empty())
        {
            throw std::invalid_argument(
                "source-keyed kernel helper requires at least one kernel "
                "sample");
        }

        std::vector<SourceKeyedSampleRows> canonicalSamples;
        canonicalSamples.reserve(faceRows.samples.size());
        for (const SourceKeyedSampleRows &sample : faceRows.samples)
        {
            SourceKeyedSampleRows canonicalSample;
            for (int rowIndex = 0;
                 rowIndex < kDerivativeRowCount;
                 ++rowIndex)
            {
                canonicalSample.rows[rowIndex] =
                    canonicalize_derivative_row(
                        sample.rows[rowIndex],
                        canonicalSourceIds,
                        input.sourceCount);
            }
            for (std::size_t source = 0;
                 source <
                 canonicalSample.rows[5].coefficients.size();
                 ++source)
            {
                if (canonicalSample.rows[5].coefficients[source] !=
                    canonicalSample.rows[6].coefficients[source])
                {
                    throw std::invalid_argument(
                        "source-keyed kernel helper rejected mixed-row "
                        "drift");
                }
            }
            canonicalSamples.push_back(std::move(canonicalSample));
        }

        SourceMappingView canonicalMapping = mapping;
        canonicalMapping.originalSourceIds = canonicalSourceIds;
        prepared.faces.push_back(
            PreparedSourceKeyedFace{std::move(canonicalMapping),
                                    std::move(canonicalSamples),
                                    canonicalForces});
    }
    return prepared;
}

std::vector<SourceForceKinds> accumulate_source_keyed_force_contributions(
    const PreparedSourceKeyedKernelCall &prepared)
{
    if (prepared.sourceCount <= 0)
    {
        throw std::invalid_argument(
            "source-keyed force accumulation requires a positive source "
            "count");
    }
    std::vector<SourceForceKinds> accumulated(prepared.sourceCount);
    for (const PreparedSourceKeyedFace &face : prepared.faces)
    {
        if (face.mapping.originalSourceIds.size() != face.forces.size())
        {
            throw std::invalid_argument(
                "source-keyed force accumulation rejected force "
                "cardinality drift");
        }
        for (std::size_t position = 0;
             position < face.mapping.originalSourceIds.size();
             ++position)
        {
            const int sourceId = face.mapping.originalSourceIds[position];
            if (sourceId < 0 || sourceId >= prepared.sourceCount)
            {
                throw std::invalid_argument(
                    "source-keyed force accumulation rejected an "
                    "out-of-range source id");
            }
            for (int kind = 0; kind < kForceKindCount; ++kind)
            {
                for (int axis = 0; axis < kAxisCount; ++axis)
                {
                    accumulated[sourceId][kind][axis] +=
                        face.forces[position][kind][axis];
                }
            }
        }
    }
    return accumulated;
}

void scatter_source_keyed_face_forces_to_component_buffer(
    const PreparedSourceKeyedFace &face,
    const int sourceCount,
    SourceForceComponentBuffer &componentBuffer)
{
    const std::size_t expectedComponents =
        static_cast<std::size_t>(sourceCount) *
        kForceComponentsPerSource;
    if (sourceCount <= 0 ||
        componentBuffer.size() != expectedComponents ||
        face.mapping.faceIndex < 0 ||
        !face.mapping.productionOneRingEmpty ||
        face.mapping.originalSourceIds.empty() ||
        face.mapping.originalSourceIds.size() != face.forces.size())
    {
        throw std::invalid_argument(
            "source-keyed component scatter rejected buffer/force "
            "cardinality drift");
    }
    if (!std::all_of(componentBuffer.begin(),
                     componentBuffer.end(),
                     [](const double value) {
                         return std::isfinite(value);
                     }))
    {
        throw std::invalid_argument(
            "source-keyed component scatter rejected nonfinite destination "
            "data");
    }

    if (!std::is_sorted(face.mapping.originalSourceIds.begin(),
                        face.mapping.originalSourceIds.end()))
    {
        throw std::invalid_argument(
            "source-keyed component scatter requires canonical source "
            "order");
    }
    std::unordered_set<int> seen;
    for (std::size_t position = 0;
         position < face.mapping.originalSourceIds.size();
         ++position)
    {
        const int sourceId = face.mapping.originalSourceIds[position];
        if (sourceId < 0 || sourceId >= sourceCount ||
            !seen.insert(sourceId).second)
        {
            throw std::invalid_argument(
                "source-keyed component scatter rejected source mapping "
                "drift");
        }
        for (const Vec3 &force : face.forces[position])
        {
            if (!std::all_of(force.begin(), force.end(), [](double value) {
                    return std::isfinite(value);
                }))
            {
                throw std::invalid_argument(
                    "source-keyed component scatter rejected nonfinite "
                    "force data");
            }
        }
    }

    std::vector<std::pair<std::size_t, double>> staged;
    staged.reserve(face.mapping.originalSourceIds.size() *
                   kForceComponentsPerSource);
    for (std::size_t position = 0;
         position < face.mapping.originalSourceIds.size();
         ++position)
    {
        const int sourceId = face.mapping.originalSourceIds[position];
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                const std::size_t component =
                    static_cast<std::size_t>(sourceId) *
                        kForceComponentsPerSource +
                    kind * kAxisCount + axis;
                const double updated =
                    componentBuffer[component] +
                    face.forces[position][kind][axis];
                if (!std::isfinite(updated))
                {
                    throw std::invalid_argument(
                        "source-keyed component scatter produced nonfinite "
                        "destination data");
                }
                staged.emplace_back(component, updated);
            }
        }
    }
    for (const auto &update : staged)
    {
        componentBuffer[update.first] = update.second;
    }
}

std::vector<SourceForceKinds> reduce_source_keyed_force_component_buffers(
    const std::vector<SourceForceComponentBuffer> &componentBuffers,
    const int sourceCount)
{
    const std::size_t expectedComponents =
        static_cast<std::size_t>(sourceCount) *
        kForceComponentsPerSource;
    if (sourceCount <= 0 || componentBuffers.empty())
    {
        throw std::invalid_argument(
            "source-keyed component reduction requires positive source and "
            "buffer counts");
    }
    for (const SourceForceComponentBuffer &buffer : componentBuffers)
    {
        if (buffer.size() != expectedComponents ||
            !std::all_of(buffer.begin(), buffer.end(), [](double value) {
                return std::isfinite(value);
            }))
        {
            throw std::invalid_argument(
                "source-keyed component reduction rejected malformed "
                "thread-buffer data");
        }
    }

    std::vector<SourceForceKinds> reduced(sourceCount);
    for (int source = 0; source < sourceCount; ++source)
    {
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                const std::size_t component =
                    static_cast<std::size_t>(source) *
                        kForceComponentsPerSource +
                    kind * kAxisCount + axis;
                double sum = 0.0;
                for (const SourceForceComponentBuffer &buffer :
                     componentBuffers)
                {
                    sum += buffer[component];
                }
                if (!std::isfinite(sum))
                {
                    throw std::invalid_argument(
                        "source-keyed component reduction produced nonfinite "
                        "output");
                }
                reduced[source][kind][axis] = sum;
            }
        }
    }
    return reduced;
}

void publish_source_keyed_membrane_forces_to_vertices(
    const std::vector<SourceForceKinds> &sourceForces,
    Mesh &mesh)
{
    if (sourceForces.empty() ||
        sourceForces.size() != mesh.vertices.size())
    {
        throw std::invalid_argument(
            "source-keyed vertex-force publication rejected source/vertex "
            "cardinality drift");
    }
    if (!std::all_of(mesh.faces.begin(),
                     mesh.faces.end(),
                     [](const Face &face) {
                         return face.oneRingVertices.empty();
                     }))
    {
        throw std::invalid_argument(
            "source-keyed vertex-force publication requires empty "
            "production one-rings");
    }

    std::vector<SourceForceKinds> staged = sourceForces;
    for (std::size_t source = 0; source < staged.size(); ++source)
    {
        const Vertex &vertex = mesh.vertices[source];
        if (vertex.index != static_cast<int>(source))
        {
            throw std::invalid_argument(
                "source-keyed vertex-force publication rejected vertex "
                "identity drift");
        }
        const std::array<const Matrix *, kForceKindCount> destinations{{
            &vertex.force.forceCurvature,
            &vertex.force.forceArea,
            &vertex.force.forceVolume}};
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            const Matrix *destination = destinations[kind];
            if (destination->mat == nullptr ||
                destination->nrow() != kAxisCount ||
                destination->ncol() != 1)
            {
                throw std::invalid_argument(
                    "source-keyed vertex-force publication rejected "
                    "destination shape drift");
            }
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                if (!std::isfinite(staged[source][kind][axis]))
                {
                    throw std::invalid_argument(
                        "source-keyed vertex-force publication rejected "
                        "nonfinite force data");
                }
            }
        }
    }

    // All validation and allocation complete before the first Mesh write.
    for (std::size_t source = 0; source < staged.size(); ++source)
    {
        Vertex &vertex = mesh.vertices[source];
        const std::array<Matrix *, kForceKindCount> destinations{{
            &vertex.force.forceCurvature,
            &vertex.force.forceArea,
            &vertex.force.forceVolume}};
        for (int kind = 0; kind < kForceKindCount; ++kind)
        {
            for (int axis = 0; axis < kAxisCount; ++axis)
            {
                destinations[kind]->set(
                    axis, 0, staged[source][kind][axis]);
            }
        }
    }
}
} // namespace slimed::source_keyed_kernel
