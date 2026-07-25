#include "io/io.hpp"
#include "mesh/Mesh.hpp"

#include <algorithm>
#include <array>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <string>
#include <vector>

namespace
{
constexpr int kFaceCount = 8;
constexpr int kSourceCount = 6;
constexpr int kForceKinds = 3;
constexpr int kAxes = 3;
constexpr int kComponents = kSourceCount * kForceKinds * kAxes;

struct FaceMapping
{
    int face = -1;
    std::array<int, 3> orientedVertices{};
    std::vector<int> sourceIds;
};

struct Validation
{
    bool passed = false;
    std::string reason;
    std::array<std::vector<int>, kFaceCount> derivedSourceIds;
};

class ScopedCoutSilencer
{
  public:
    ScopedCoutSilencer() : original_(std::cout.rdbuf(buffer_.rdbuf())) {}
    ~ScopedCoutSilencer() { std::cout.rdbuf(original_); }

  private:
    std::ostringstream buffer_;
    std::streambuf *original_;
};

bool read_mapping(const std::string &path,
                  std::vector<int> &originalSourceIds,
                  std::array<FaceMapping, kFaceCount> &mappings)
{
    std::ifstream input(path);
    int sourceCount = 0;
    if (!(input >> sourceCount) || sourceCount != kSourceCount)
    {
        return false;
    }
    originalSourceIds.resize(sourceCount);
    for (int &source : originalSourceIds)
    {
        if (!(input >> source))
        {
            return false;
        }
    }

    int faceCount = 0;
    if (!(input >> faceCount) || faceCount != kFaceCount)
    {
        return false;
    }
    for (int expectedFace = 0; expectedFace < kFaceCount; ++expectedFace)
    {
        FaceMapping &mapping = mappings[expectedFace];
        int coverageCount = 0;
        if (!(input >> mapping.face) || mapping.face != expectedFace)
        {
            return false;
        }
        for (int &vertex : mapping.orientedVertices)
        {
            if (!(input >> vertex))
            {
                return false;
            }
        }
        if (!(input >> coverageCount) || coverageCount < 0)
        {
            return false;
        }
        mapping.sourceIds.resize(coverageCount);
        for (int &source : mapping.sourceIds)
        {
            if (!(input >> source))
            {
                return false;
            }
        }
    }
    int extra = 0;
    return !(input >> extra);
}

std::vector<int> derive_source_ids(const Mesh &mesh, const Face &face)
{
    std::set<int> sources;
    for (const int vertex : face.adjacentVertices)
    {
        sources.insert(vertex);
        for (const int neighbor : mesh.vertices[vertex].adjacentVertices)
        {
            sources.insert(neighbor);
        }
    }
    return std::vector<int>(sources.begin(), sources.end());
}

Validation validate_mapping(
    const Mesh &mesh,
    const std::vector<int> &originalSourceIds,
    const std::array<FaceMapping, kFaceCount> &mappings)
{
    Validation result;
    const std::vector<int> expectedSources{0, 1, 2, 3, 4, 5};
    if (originalSourceIds != expectedSources)
    {
        result.reason = "OpenSubdiv original source ids are not exactly 0..5";
        return result;
    }
    if (mesh.vertices.size() != kSourceCount ||
        mesh.faces.size() != kFaceCount)
    {
        result.reason = "production topology has unexpected dimensions";
        return result;
    }
    for (int source = 0; source < kSourceCount; ++source)
    {
        if (mesh.vertices[source].index != source)
        {
            result.reason = "production vertex index is not its source id";
            return result;
        }
        if (mesh.vertices[source].adjacentVertices.size() != 4u)
        {
            result.reason = "production source vertex is not valence four";
            return result;
        }
    }

    for (int faceIndex = 0; faceIndex < kFaceCount; ++faceIndex)
    {
        const Face &face = mesh.faces[faceIndex];
        const FaceMapping &mapping = mappings[faceIndex];
        if (face.index != faceIndex || mapping.face != faceIndex)
        {
            result.reason = "face identity is not stable";
            return result;
        }
        if (face.isGhost || face.isBoundary)
        {
            result.reason = "approved fixture contains a nonphysical face";
            return result;
        }
        if (!face.oneRingVertices.empty())
        {
            result.reason =
                "proof must not populate production Face::oneRingVertices";
            return result;
        }
        for (int corner = 0; corner < 3; ++corner)
        {
            if (face.adjacentVertices[corner] !=
                mapping.orientedVertices[corner])
            {
                result.reason =
                    "OpenSubdiv face orientation differs from production";
                return result;
            }
        }

        result.derivedSourceIds[faceIndex] =
            derive_source_ids(mesh, face);
        if (result.derivedSourceIds[faceIndex] != expectedSources)
        {
            result.reason =
                "production topology did not derive all six source ids";
            return result;
        }
        if (mapping.sourceIds != result.derivedSourceIds[faceIndex])
        {
            result.reason =
                "OpenSubdiv source coverage differs from production topology";
            return result;
        }
    }

    result.passed = true;
    result.reason = "production topology and OpenSubdiv source ids agree";
    return result;
}

bool sentinel_scatter_passed(
    const std::array<FaceMapping, kFaceCount> &mappings)
{
    std::array<double, kComponents> actual{};
    std::array<std::array<std::array<double, kAxes>, kForceKinds>,
               kSourceCount>
        expectedBySource{};

    for (int face = 0; face < kFaceCount; ++face)
    {
        for (int position = 0;
             position < static_cast<int>(mappings[face].sourceIds.size());
             ++position)
        {
            const int source = mappings[face].sourceIds[position];
            if (source < 0 || source >= kSourceCount)
            {
                return false;
            }
            for (int kind = 0; kind < kForceKinds; ++kind)
            {
                for (int axis = 0; axis < kAxes; ++axis)
                {
                    const double sentinel =
                        100000.0 * (face + 1) +
                        1000.0 * (position + 1) +
                        10.0 * (kind + 1) + axis + 1.0;
                    const int destination =
                        source * 9 + kind * 3 + axis;
                    actual[destination] += sentinel;
                }
            }
        }
    }

    // The expected layout is assembled independently from the approved
    // canonical source order rather than the candidate mapping.
    for (int face = 0; face < kFaceCount; ++face)
    {
        for (int source = 0; source < kSourceCount; ++source)
        {
            for (int kind = 0; kind < kForceKinds; ++kind)
            {
                for (int axis = 0; axis < kAxes; ++axis)
                {
                    expectedBySource[source][kind][axis] +=
                        100000.0 * (face + 1) +
                        1000.0 * (source + 1) +
                        10.0 * (kind + 1) + axis + 1.0;
                }
            }
        }
    }

    int destination = 0;
    for (int source = 0; source < kSourceCount; ++source)
    {
        for (int kind = 0; kind < kForceKinds; ++kind)
        {
            for (int axis = 0; axis < kAxes; ++axis)
            {
                if (actual[destination] !=
                    expectedBySource[source][kind][axis])
                {
                    return false;
                }
                ++destination;
            }
        }
    }
    return destination == kComponents;
}

void print_int_array(const std::vector<int> &values)
{
    std::cout << '[';
    for (std::size_t index = 0; index < values.size(); ++index)
    {
        if (index != 0)
        {
            std::cout << ',';
        }
        std::cout << values[index];
    }
    std::cout << ']';
}
} // namespace

int main(int argc, char **argv)
{
    if (argc != 4)
    {
        std::cerr << "usage: adapter vertices.csv faces.csv mapping.txt\n";
        return 2;
    }

    std::vector<int> originalSourceIds;
    std::array<FaceMapping, kFaceCount> mappings;
    if (!read_mapping(argv[3], originalSourceIds, mappings))
    {
        std::cerr << "failed to read topology/source mapping input\n";
        return 3;
    }

    Param param;
    param.VERBOSE_MODE = false;
    param.boundaryCondition = BoundaryType::Fixed;
    param.subDivideTimes = 2;
    const auto verticesData = read_data_from_csv<double>(argv[1]);
    const auto facesData = read_data_from_csv<int>(argv[2]);
    Mesh mesh(param);
    {
        ScopedCoutSilencer silence;
        mesh.setup_from_vertices_faces(verticesData, facesData);
    }

    bool coordinatesMatch = mesh.vertices.size() == verticesData.size();
    for (std::size_t source = 0;
         coordinatesMatch && source < verticesData.size();
         ++source)
    {
        coordinatesMatch =
            mesh.vertices[source].index == static_cast<int>(source);
        for (int axis = 0; coordinatesMatch && axis < kAxes; ++axis)
        {
            coordinatesMatch =
                mesh.vertices[source].coord(axis, 0) ==
                verticesData[source][axis];
        }
    }

    const Validation canonical =
        validate_mapping(mesh, originalSourceIds, mappings);
    const bool scatterPassed = sentinel_scatter_passed(mappings);

    auto duplicate = mappings;
    duplicate[0].sourceIds.back() =
        duplicate[0].sourceIds[duplicate[0].sourceIds.size() - 2];
    const bool duplicateRejected =
        !validate_mapping(mesh, originalSourceIds, duplicate).passed;

    auto missing = mappings;
    missing[0].sourceIds.pop_back();
    const bool missingRejected =
        !validate_mapping(mesh, originalSourceIds, missing).passed;

    auto outOfRange = mappings;
    outOfRange[0].sourceIds.back() = kSourceCount;
    const bool outOfRangeRejected =
        !validate_mapping(mesh, originalSourceIds, outOfRange).passed;

    auto wrongOrientation = mappings;
    std::swap(wrongOrientation[0].orientedVertices[1],
              wrongOrientation[0].orientedVertices[2]);
    const bool orientationRejected =
        !validate_mapping(mesh, originalSourceIds, wrongOrientation).passed;

    bool productionOneRingsEmpty = true;
    for (const Face &face : mesh.faces)
    {
        productionOneRingsEmpty =
            productionOneRingsEmpty && face.oneRingVertices.empty();
    }

    const bool mutationRejectionsPassed =
        duplicateRejected && missingRejected &&
        outOfRangeRejected && orientationRejected;
    const bool passed =
        coordinatesMatch && canonical.passed && scatterPassed &&
        productionOneRingsEmpty && mutationRejectionsPassed;

    std::cout << '{';
    std::cout << "\"kind\":"
                 "\"proof_only_valence4_topology_source_mapping_adapter\",";
    std::cout << "\"proof_only\":true,";
    std::cout << "\"topology_source_mapping_adapter_design\":true,";
    std::cout << "\"not_production_routing\":true,";
    std::cout << "\"production_route_enabled\":false,";
    std::cout << "\"scientifically_approved\":false,";
    std::cout << "\"actual_production_force_path_executed\":false,";
    std::cout << "\"fixture\":\"closed_valence4_octahedron\",";
    std::cout << "\"coordinates_match_fixture\":"
              << (coordinatesMatch ? "true" : "false") << ',';
    std::cout << "\"production_topology_source_identity_passed\":"
              << (canonical.passed ? "true" : "false") << ',';
    std::cout << "\"production_one_rings_populated\":false,";
    std::cout << "\"production_one_rings_expected_empty\":"
              << (productionOneRingsEmpty ? "true" : "false") << ',';
    std::cout << "\"original_source_ids\":";
    print_int_array(originalSourceIds);
    std::cout << ",\"per_face_source_ids\":[";
    for (int face = 0; face < kFaceCount; ++face)
    {
        if (face != 0)
        {
            std::cout << ',';
        }
        print_int_array(canonical.derivedSourceIds[face]);
    }
    std::cout << "],";
    std::cout << "\"independent_sentinel_scatter_oracle_passed\":"
              << (scatterPassed ? "true" : "false") << ',';
    std::cout << "\"duplicate_source_rejected\":"
              << (duplicateRejected ? "true" : "false") << ',';
    std::cout << "\"missing_source_rejected\":"
              << (missingRejected ? "true" : "false") << ',';
    std::cout << "\"out_of_range_source_rejected\":"
              << (outOfRangeRejected ? "true" : "false") << ',';
    std::cout << "\"oriented_face_mismatch_rejected\":"
              << (orientationRejected ? "true" : "false") << ',';
    std::cout << "\"mutation_rejections_passed\":"
              << (mutationRejectionsPassed ? "true" : "false") << ',';
    std::cout << "\"limitation\":"
                 "\"approved octahedron only; no generic valence-4 route\",";
    std::cout << "\"passed\":" << (passed ? "true" : "false");
    std::cout << "}\n";
    return passed ? 0 : 1;
}
