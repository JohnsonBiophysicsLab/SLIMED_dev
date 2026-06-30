#include "mesh/OpenSubdiv_regular_evaluator.hpp"

#include "mesh/Face.hpp"
#include "mesh/Mesh.hpp"

#include <cstdlib>
#include <array>
#include <stdexcept>
#include <string>

namespace
{
constexpr const char *kOpenSubdivRegularEnv =
    "SLIMED_USE_OPENSUBDIV_REGULAR";

bool env_value_is_enabled(const char *value)
{
    if (value == nullptr || value[0] == '\0')
    {
        return false;
    }
    const std::string text(value);
    return text != "0" && text != "false" && text != "FALSE" &&
           text != "off" && text != "OFF";
}
} // namespace

bool opensubdiv_regular_production_routing_requested()
{
    return env_value_is_enabled(std::getenv(kOpenSubdivRegularEnv));
}

#ifdef USE_OPENSUBDIV_REGULAR

#include <opensubdiv/far/stencilTable.h>
#include <opensubdiv/far/stencilTableFactory.h>
#include <opensubdiv/far/topologyDescriptor.h>
#include <opensubdiv/far/topologyRefinerFactory.h>

#include <memory>

using namespace OpenSubdiv;

namespace
{
constexpr int kRegularControlPointCount = 12;
constexpr int kDerivativeRowCount = 7;

struct RefinerDeleter
{
    void operator()(Far::TopologyRefiner *refiner) const
    {
        delete refiner;
    }
};

std::unique_ptr<Far::TopologyRefiner, RefinerDeleter>
create_refiner_for_mesh(const Mesh &mesh)
{
    using Descriptor = Far::TopologyDescriptor;

    std::vector<int> vertsPerFace;
    std::vector<int> vertIndices;
    vertsPerFace.reserve(mesh.faces.size());
    vertIndices.reserve(mesh.faces.size() * 3);

    for (const Face &face : mesh.faces)
    {
        if (face.adjacentVertices.size() != 3)
        {
            throw std::runtime_error(
                "OpenSubdiv regular routing requires triangular faces.");
        }
        vertsPerFace.push_back(3);
        for (int vertex : face.adjacentVertices)
        {
            if (vertex < 0 ||
                vertex >= static_cast<int>(mesh.vertices.size()))
            {
                throw std::runtime_error(
                    "OpenSubdiv regular routing found an invalid face vertex index.");
            }
            vertIndices.push_back(vertex);
        }
    }

    Descriptor desc;
    desc.numVertices = static_cast<int>(mesh.vertices.size());
    desc.numFaces = static_cast<int>(vertsPerFace.size());
    desc.numVertsPerFace = vertsPerFace.data();
    desc.vertIndicesPerFace = vertIndices.data();

    Sdc::Options options;
    options.SetVtxBoundaryInterpolation(Sdc::Options::VTX_BOUNDARY_EDGE_ONLY);

    return std::unique_ptr<Far::TopologyRefiner, RefinerDeleter>(
        Far::TopologyRefinerFactory<Descriptor>::Create(
            desc,
            Far::TopologyRefinerFactory<Descriptor>::Options(
                Sdc::SCHEME_LOOP, options)));
}

double stencil_weight_for_source(const Far::LimitStencil &stencil,
                                 const float *weights,
                                 const int sourceId)
{
    double result = 0.0;
    const Far::Index *indices = stencil.GetVertexIndices();
    for (int index = 0; index < stencil.GetSize(); ++index)
    {
        if (indices[index] == sourceId)
        {
            result += static_cast<double>(weights[index]);
        }
    }
    return result;
}

Matrix shape_function_from_stencil(const Far::LimitStencil &stencil,
                                   const std::vector<int> &sourceIds)
{
    const std::array<const float *, kDerivativeRowCount> rowWeights = {
        stencil.GetWeights(),
        stencil.GetDuWeights(),
        stencil.GetDvWeights(),
        stencil.GetDuuWeights(),
        stencil.GetDvvWeights(),
        stencil.GetDuvWeights(),
        stencil.GetDuvWeights(),
    };

    Matrix shapeFunction(kDerivativeRowCount, kRegularControlPointCount, true);
    for (int row = 0; row < kDerivativeRowCount; ++row)
    {
        for (int col = 0; col < kRegularControlPointCount; ++col)
        {
            shapeFunction.set(row,
                              col,
                              stencil_weight_for_source(stencil,
                                                        rowWeights[row],
                                                        sourceIds[col]));
        }
    }
    return shapeFunction;
}

std::vector<Matrix> shape_functions_for_face(
    const Mesh &mesh,
    const Face &face,
    Far::TopologyRefiner &refiner)
{
    if (face.oneRingVertices.size() != kRegularControlPointCount)
    {
        throw std::runtime_error(
            "OpenSubdiv regular routing is limited to 12-control regular faces.");
    }
    if (face.index < 0 || face.index >= static_cast<int>(mesh.faces.size()))
    {
        throw std::runtime_error(
            "OpenSubdiv regular routing requires Face::index to address Mesh::faces.");
    }
    if (mesh.param.shapeFunctions.size() != 3u ||
        mesh.param.gaussQuadratureCoeff.nrow() != 3)
    {
        throw std::runtime_error(
            "OpenSubdiv regular routing requires the frozen three-sample regular quadrature plan.");
    }

    std::vector<float> s(mesh.param.shapeFunctions.size(), 0.0f);
    std::vector<float> t(mesh.param.shapeFunctions.size(), 0.0f);

    for (int sample = 0; sample < static_cast<int>(mesh.param.shapeFunctions.size());
         ++sample)
    {
        Matrix vwu = mesh.param.VWU.get_row(sample);
        s[sample] = static_cast<float>(vwu.get(0, 0));
        t[sample] = static_cast<float>(vwu.get(0, 1));
    }

    Far::LimitStencilTableFactory::LocationArray location;
    location.ptexIdx = face.index;
    location.numLocations = static_cast<int>(mesh.param.shapeFunctions.size());
    location.s = s.data();
    location.t = t.data();

    Far::LimitStencilTableFactory::LocationArrayVec locations;
    locations.push_back(location);

    Far::LimitStencilTableFactory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;

    const Far::LimitStencilTable *rawStencils =
        Far::LimitStencilTableFactory::Create(refiner,
                                              locations,
                                              0,
                                              0,
                                              stencilOptions);
    if (rawStencils == nullptr)
    {
        throw std::runtime_error(
            "OpenSubdiv regular routing failed to create limit stencils.");
    }
    std::unique_ptr<const Far::LimitStencilTable> stencils(rawStencils);

    std::vector<Matrix> shapeFunctions;
    shapeFunctions.reserve(mesh.param.shapeFunctions.size());
    for (int sample = 0; sample < static_cast<int>(mesh.param.shapeFunctions.size());
         ++sample)
    {
        shapeFunctions.push_back(
            shape_function_from_stencil(stencils->GetLimitStencil(sample),
                                        face.oneRingVertices));
    }
    return shapeFunctions;
}
} // namespace

std::vector<std::vector<Matrix>>
build_opensubdiv_regular_shape_functions_by_face(const Mesh &mesh)
{
    if (!opensubdiv_regular_production_routing_requested())
    {
        return {};
    }

    auto refiner = create_refiner_for_mesh(mesh);
    if (!refiner)
    {
        throw std::runtime_error(
            "OpenSubdiv regular routing failed to create topology refiner.");
    }

    Far::TopologyRefiner::AdaptiveOptions adaptiveOptions(3);
    refiner->RefineAdaptive(adaptiveOptions);

    std::vector<std::vector<Matrix>> routedShapeFunctions(mesh.faces.size());
    for (const Face &face : mesh.faces)
    {
        if (face.isBoundary || face.isGhost)
        {
            continue;
        }
        if (face.oneRingVertices.size() != kRegularControlPointCount)
        {
            throw std::runtime_error(
                "OpenSubdiv regular routing was requested, but a non-regular "
                "face was encountered. This route is limited to regular "
                "12-control faces.");
        }
        routedShapeFunctions[face.index] =
            shape_functions_for_face(mesh, face, *refiner);
    }
    return routedShapeFunctions;
}

#else

std::vector<std::vector<Matrix>>
build_opensubdiv_regular_shape_functions_by_face(const Mesh &mesh)
{
    (void)mesh;
    if (opensubdiv_regular_production_routing_requested())
    {
        throw std::runtime_error(
            "SLIMED_USE_OPENSUBDIV_REGULAR was set, but this binary was not "
            "built with USE_OPENSUBDIV_REGULAR=1 and an explicit "
            "OPENSUBDIV_ROOT. Default builds remain OpenSubdiv-free.");
    }
    return {};
}

#endif
