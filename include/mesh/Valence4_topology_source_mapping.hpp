/**
 * @file Valence4_topology_source_mapping.hpp
 * @brief Guarded source identity for the approved closed valence-4 topology.
 */

#pragma once

#include <array>
#include <string>
#include <vector>

class Mesh;

struct Valence4FaceTopologySourceMapping
{
    int faceIndex = -1;
    std::array<int, 3> orientedFaceVertices{{-1, -1, -1}};
    std::vector<int> originalSourceIds;
};

struct Valence4TopologySourceMappingResult
{
    bool supported = false;
    std::string rejectionReason;
    std::vector<Valence4FaceTopologySourceMapping> byFace;
};

/**
 * @brief Build a backend-neutral source mapping for the approved octahedron.
 *
 * This function does not populate Face::oneRingVertices and does not enable a
 * production force route. Unsupported topology returns supported=false with a
 * non-empty rejection reason and an empty mapping.
 */
Valence4TopologySourceMappingResult
build_guarded_valence4_topology_source_mapping(const Mesh &mesh);
