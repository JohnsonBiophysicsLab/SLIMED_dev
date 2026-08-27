#include "mesh/Mesh.hpp"

#include <sstream>

namespace
{
enum class OppositeNodeSearchState
{
    Unique,
    Missing,
    Ambiguous,
    InvalidVertexIndex
};

struct OppositeNodeSearchResult
{
    OppositeNodeSearchState state = OppositeNodeSearchState::Missing;
    int vertex = -1;
};

OppositeNodeSearchResult find_unique_opposite_node_index(
    const std::vector<Vertex> &vertices,
    const int node1,
    const int node2,
    const int node3)
{
    const auto valid_vertex_index = [&vertices](const int vertex) {
        return vertex >= 0 &&
               static_cast<std::size_t>(vertex) < vertices.size();
    };
    if (!valid_vertex_index(node1) || !valid_vertex_index(node2) ||
        !valid_vertex_index(node3))
    {
        return {OppositeNodeSearchState::InvalidVertexIndex, -1};
    }

    std::vector<int> candidates;
    for (int i = 0; i < vertices[node1].adjacentVertices.size(); ++i)
    {
        const int candidate1 = vertices[node1].adjacentVertices[i];
        for (int j = 0; j < vertices[node2].adjacentVertices.size(); ++j)
        {
            const int candidate2 = vertices[node2].adjacentVertices[j];
            if (candidate1 == candidate2 && candidate1 != node3)
            {
                if (!valid_vertex_index(candidate1))
                {
                    return {OppositeNodeSearchState::InvalidVertexIndex, -1};
                }
                if (std::find(candidates.begin(), candidates.end(), candidate1) ==
                    candidates.end())
                {
                    candidates.push_back(candidate1);
                }
            }
        }
    }

    if (candidates.empty())
    {
        return {OppositeNodeSearchState::Missing, -1};
    }
    if (candidates.size() != 1u)
    {
        return {OppositeNodeSearchState::Ambiguous, -1};
    }
    return {OppositeNodeSearchState::Unique, candidates.front()};
}

bool is_legacy_one_ring_rejection(const LegacyOneRingReasonCode code)
{
    switch (code)
    {
    case LegacyOneRingReasonCode::ReadyRegular:
    case LegacyOneRingReasonCode::ReadyAllValenceFiveAliased:
    case LegacyOneRingReasonCode::AdjacentVertexFaceCardinalityMismatch:
    case LegacyOneRingReasonCode::SkippedGhostFace:
    case LegacyOneRingReasonCode::UnsupportedCornerValence:
        return false;
    case LegacyOneRingReasonCode::InvalidFaceCornerCount:
    case LegacyOneRingReasonCode::InvalidCornerVertexIndex:
    case LegacyOneRingReasonCode::NoAdjacentFaceCountMatch:
    case LegacyOneRingReasonCode::AmbiguousAdjacentFaceCountMatch:
    case LegacyOneRingReasonCode::InvalidAdjacentVertexIndex:
    case LegacyOneRingReasonCode::OppositeNodeMissing:
    case LegacyOneRingReasonCode::OppositeNodeAmbiguous:
        return true;
    }
    return true;
}
} // namespace

const char *legacy_one_ring_reason_code_name(const LegacyOneRingReasonCode code)
{
    switch (code)
    {
    case LegacyOneRingReasonCode::ReadyRegular:
        return "READY_REGULAR";
    case LegacyOneRingReasonCode::ReadyAllValenceFiveAliased:
        return "READY_ALL_VALENCE_FIVE_ALIASED";
    case LegacyOneRingReasonCode::SkippedGhostFace:
        return "SKIPPED_GHOST_FACE";
    case LegacyOneRingReasonCode::UnsupportedCornerValence:
        return "UNSUPPORTED_CORNER_VALENCE";
    case LegacyOneRingReasonCode::InvalidFaceCornerCount:
        return "INVALID_FACE_CORNER_COUNT";
    case LegacyOneRingReasonCode::InvalidCornerVertexIndex:
        return "INVALID_CORNER_VERTEX_INDEX";
    case LegacyOneRingReasonCode::NoAdjacentFaceCountMatch:
        return "NO_ADJACENT_FACE_COUNT_MATCH";
    case LegacyOneRingReasonCode::AmbiguousAdjacentFaceCountMatch:
        return "AMBIGUOUS_ADJACENT_FACE_COUNT_MATCH";
    case LegacyOneRingReasonCode::AdjacentVertexFaceCardinalityMismatch:
        return "ADJACENT_VERTEX_FACE_CARDINALITY_MISMATCH";
    case LegacyOneRingReasonCode::InvalidAdjacentVertexIndex:
        return "INVALID_ADJACENT_VERTEX_INDEX";
    case LegacyOneRingReasonCode::OppositeNodeMissing:
        return "OPPOSITE_NODE_MISSING";
    case LegacyOneRingReasonCode::OppositeNodeAmbiguous:
        return "OPPOSITE_NODE_AMBIGUOUS";
    }
    return "UNKNOWN_LEGACY_ONE_RING_REASON";
}


void Mesh::set_adjacent_faces_of_vertices_sorted()
{
    // 1. Get adjacent faces unsorted
    // Initialize vector of empty vectors for adjacent faces
    vector<vector<int>> adjFaces(vertices.size());
    
    // Populate adjacent faces for each vertex
    for (int j = 0; j < faces.size(); j++)
    {
        for (int k = 0; k < 3; k++)
        {
            int i = faces[j].adjacentVertices[k];
            adjFaces[i].push_back(j);
        }
    }
    
    // Transfer adjacent faces from temp vector to each vertex
    for (int i = 0; i < vertices.size(); i++)
    {
        vertices[i].adjacentFaces = std::move(adjFaces[i]);
    }

    if (param.VERBOSE_MODE)
    {
        std::cout << "[Mesh::set_adjacent_faces_of_vertices_sorted] Got adjacent faces unsorted." << std::endl;
    }

    // 2. Sort faces so that adjacentFaces that are adjacent to each
    // other are of +/- 1 index.
    for (int j = 0; j < param.nFaceY + 1; j++) // iterate along y-axis
    {
        for (int i = 0; i < param.nFaceX + 1; i++) // iterate along x-axis
        {
            // initialize adjacent vertex indices
            std::vector<int> adjacentFacesSorted(6, 0);
            if (j & 1) // j is odd
            {
                adjacentFacesSorted[0] = 2 * (param.nFaceX * (j - 1) + i) - 2;
                adjacentFacesSorted[1] = 2 * (param.nFaceX * j + i) - 2;
                adjacentFacesSorted[2] = 2 * (param.nFaceX * j + i) - 1;
                adjacentFacesSorted[3] = 2 * (param.nFaceX * j + i);
                adjacentFacesSorted[4] = 2 * (param.nFaceX * (j - 1) + i);
                adjacentFacesSorted[5] = 2 * (param.nFaceX * (j - 1) + i) - 1;
            }
            else // j is even
            {
                adjacentFacesSorted[0] = 2 * (param.nFaceX * (j - 1) + i) - 1;
                adjacentFacesSorted[1] = 2 * (param.nFaceX * j + i) - 1;
                adjacentFacesSorted[2] = 2 * (param.nFaceX * j + i);
                adjacentFacesSorted[3] = 2 * (param.nFaceX * j + i) + 1;
                adjacentFacesSorted[4] = 2 * (param.nFaceX * (j - 1) + i) + 1;
                adjacentFacesSorted[5] = 2 * (param.nFaceX * (j - 1) + i);
            }

            // pop vertices that do not exist
            for (int k = 5; k >= 0; k--)
            {
                std::vector<int> *adjacentFacesUnsorted = &(vertices[(1 + param.nFaceX) * j + i].adjacentFaces);
                if (std::find(adjacentFacesUnsorted->begin(),
                              adjacentFacesUnsorted->end(),
                              adjacentFacesSorted[k]) == adjacentFacesUnsorted->end()) // if value not in unsorted
                {
                    adjacentFacesSorted.erase(adjacentFacesSorted.begin() + k);
                }
            }
            vertices[(1 + param.nFaceX) * j + i].adjacentFaces = adjacentFacesSorted;
        }
    }

    if (param.VERBOSE_MODE)
    {
        std::cout << "[Mesh::set_adjacent_faces_of_vertices_sorted] Faces sorted." << std::endl;
    }
}

/**
 * @brief Return true if two faces share edge.
 * 
 * @brief Will also return true if face1 and face2 are the same face.
 * 
 * @param face1 
 * @param face2 
 * @return true 
 * @return false 
 */
bool Mesh::faces_share_edge(const Face& face1, const Face& face2){
    // If face1 and face2 have two identical vertices then they 
    // share edge
    // Use std::set_intersection to find common elements
    std::vector<int> commonElements;
    return faces_share_edge(face1, face2, commonElements);
}

bool Mesh::faces_share_edge(const Face& face1, const Face& face2, std::vector<int>& commonElements){
    // If face1 and face2 have two identical vertices then they 
    // share edge
    // Use std::set_intersection to find common elements
    std::set_intersection(face1.adjacentVertices.begin(), face1.adjacentVertices.end(),
                          face2.adjacentVertices.begin(), face2.adjacentVertices.end(),
                          std::back_inserter(commonElements));

    // Check if there are at least two common vertices
    return commonElements.size() >= 2;
}

/**
 * @brief Set adjacentFaces properties of faces based on the current
 * geometry of mesh.
 * 
 * This function iterates over the faces of the mesh and populates the
 * adjacentFaces property of each face by finding neighboring faces that
 * share an edge.
 */
void Mesh::set_adjacent_faces_of_faces(){
    // iterate over faces and add adjacent faces
    for (int i = 0; i < faces.size(); ++i){
        // Initialize the adjacentFaces vector for the current face
        faces[i].adjacentFaces = std::vector<int>(3);
        int adjacentFaceIndex = 0;

        // Iterate over all faces to find adjacent faces
        for (int j = 0; j < faces.size(); ++j){
            // Check if faces i and j share an edge
            if (faces_share_edge(faces[i], faces[j])){
                // Add the index of the adjacent face to the current face's adjacentFaces vector
                faces[i].adjacentFaces[adjacentFaceIndex] = j;
                // Move to the next slot in the adjacentFaces vector
                ++adjacentFaceIndex;
            }
        }
    }
}


void Mesh::set_adjacent_vertices_of_vertices_sorted()
{

#pragma omp parallel for
    // iterate over vertices and add adjacent vertices of adjacent faces
    for (int i = 0; i < vertices.size(); i++)
    {
        vector<int> adjacentVerticesTmp;
        for (int j = 0; j < vertices[i].adjacentFaces.size(); j++)
        {
            int faceIndex = vertices[i].adjacentFaces[j];
            for (int k = 0; k < faces[faceIndex].adjacentVertices.size(); k++)
            {
                int vertexIndex = faces[faceIndex].adjacentVertices[k];
                if (vertexIndex != i)
                {
                    bool isListed = false;
                    // check if both vertices are in adjacent vertices of a face
                    for (int m = 0; m < adjacentVerticesTmp.size(); m++)
                    {
                        if (vertexIndex == adjacentVerticesTmp[m])
                        {
                            isListed = true;
                        }
                    }
                    if (isListed == false)
                    {
                        adjacentVerticesTmp.push_back(vertexIndex);
                    }
                }
            }
        }
        vertices[i].adjacentVertices = adjacentVerticesTmp;
    }
    if (param.VERBOSE_MODE)
    {
        std::cout << "[Mesh::set_adjacent_vertices_of_vertices_sorted] Adjacent vertices set." << std::endl;
    }
}

int Mesh::find_opposite_node_index(const int &node1, const int &node2, const int &node3)
{
    int node = -1;
    for (int i = 0; i < vertices[node1].adjacentVertices.size(); i++)
    {
        int nodetmp1 = vertices[node1].adjacentVertices[i];
        for (int j = 0; j < vertices[node2].adjacentVertices.size(); j++)
        {
            int nodetmp2 = vertices[node2].adjacentVertices[j];
            if (nodetmp1 == nodetmp2 && nodetmp1 != node3)
            {
                node = nodetmp1;
            }
        }
    }
    if (node == -1)
    {
        if (param.VERBOSE_MODE)
        {
            cout << "No efficent oneRingVerticesIndex is found! Node1 = "
                 << node1 << ", Node2 = " << node2 << ", Node3 = " << node3
                 << endl;
        }
    }
    return node;
}

/**
 * @brief Sort vertices on faces so that the unit normal vector indicates
 * the orientation of the local patch of the membrane.
 * 
 * For example, if a face has vertices A->B->C, then the unit normal vector
 * is calculated as AB x BC. This follows a "half-edge" data structure:
 * if face ABC and face BCD shares edge BC, and ABC has vertices A->B->C, then
 * on BCD, the edge sequence of BC needs to be reverse and therefore BCD has
 * vertices C->B->D.
 * 
 */
void Mesh::sort_vertices_on_faces()
{
    bool isAllFacesSorted = false;
    // Initialize a vector of booleans with given length and set all elements to false
    std::vector<bool> isFaceSorted(faces.size(), false);

    // Assume all face sort sequence will be based on faces[0]
    isFaceSorted[0] = true;

    // Loop through all faces in the mesh
    while (!isAllFacesSorted)
    {
        // Loop through all faces in the mesh
        for (int iFace = 0; iFace < faces.size(); iFace++) {
            if (!(isFaceSorted[iFace]))
            {
                for (int j = 0; j < 3; j++){
                    int jAdjFace = faces[iFace].adjacentFaces[j];
                    if (isFaceSorted[jAdjFace] && !isFaceSorted[iFace]){
                        std::vector<int> commonElements;
                        faces_share_edge(faces[iFace], faces[jAdjFace], commonElements);
                        
                        // Concatenate the first vector with itself to check for wrapping-around sequences
                        std::vector<int> extendedAdjFacesj = faces[jAdjFace].adjacentFaces;
                        extendedAdjFacesj.insert(extendedAdjFacesj.end(),
                                faces[jAdjFace].adjacentFaces.begin(),
                                faces[jAdjFace].adjacentFaces.end());
                        std::vector<int> extendedAdjFacesi = faces[iFace].adjacentFaces;
                        extendedAdjFacesi.insert(extendedAdjFacesi.end(),
                                faces[iFace].adjacentFaces.begin(),
                                faces[iFace].adjacentFaces.end());
                        
                        // If extendedAdjFacesj DOES NOT contain commonElements, reverse common Elements
                        if (std::search(extendedAdjFacesj.begin(), extendedAdjFacesj.end(),
                                commonElements.begin(), commonElements.end()) == extendedAdjFacesj.end())
                        {
                            std::reverse(commonElements.begin(), commonElements.end());
                        }

                        // If extendedAdjFacesi CONTAINS commonElemnts reverse it
                        if (std::search(extendedAdjFacesi.begin(), extendedAdjFacesi.end(),
                                commonElements.begin(), commonElements.end()) != extendedAdjFacesi.end())
                        {
                            std::reverse(faces[iFace].adjacentFaces.begin(), faces[iFace].adjacentFaces.end());
                        }

                        // Set processed flag to true
                        isFaceSorted[iFace] = true;
                    }
                }
            }
        }
        // Recalculate isAllFacesSorted
        isAllFacesSorted = true;
        for (bool value : isFaceSorted) {
            if (!value) {
                isAllFacesSorted = false;
                break;
            }
        }
    }
}

LegacyOneRingClassification Mesh::classify_legacy_one_ring(const Face &face) const
{
    LegacyOneRingClassification result;

    if (face.isGhost)
    {
        result.reasonCode = LegacyOneRingReasonCode::SkippedGhostFace;
        return result;
    }
    if (face.adjacentVertices.size() != 3u)
    {
        result.reasonCode = LegacyOneRingReasonCode::InvalidFaceCornerCount;
        return result;
    }

    const auto valid_vertex_index = [this](const int vertex) {
        return vertex >= 0 &&
               static_cast<std::size_t>(vertex) < vertices.size();
    };
    for (int corner = 0; corner < 3; ++corner)
    {
        const int vertex = face.adjacentVertices[corner];
        if (!valid_vertex_index(vertex))
        {
            result.reasonCode = LegacyOneRingReasonCode::InvalidCornerVertexIndex;
            return result;
        }
        result.cornerValences[corner] = vertices[vertex].adjacentVertices.size();
        result.adjacentFaceCardinalities[corner] =
            vertices[vertex].adjacentFaces.size();
        if (result.adjacentFaceCardinalities[corner] == 5u)
        {
            result.extraordinaryCornerCandidates.push_back(corner);
        }
    }
    if (result.extraordinaryCornerCandidates.size() == 1u)
    {
        result.candidateExtraordinaryCorner =
            result.extraordinaryCornerCandidates.front();
    }

    const bool regular = std::all_of(
        result.cornerValences.begin(),
        result.cornerValences.end(),
        [](const std::size_t valence) { return valence == 6u; });
    const bool allValenceFive = std::all_of(
        result.cornerValences.begin(),
        result.cornerValences.end(),
        [](const std::size_t valence) { return valence == 5u; });
    if (!regular && !allValenceFive)
    {
        result.reasonCode = LegacyOneRingReasonCode::UnsupportedCornerValence;
        return result;
    }

    int d4 = -1;
    int d7 = -1;
    int d8 = -1;
    bool hasCardinalityMismatch = false;
    if (regular)
    {
        d4 = face.adjacentVertices[0];
        d7 = face.adjacentVertices[1];
        d8 = face.adjacentVertices[2];
    }
    else
    {
        if (result.extraordinaryCornerCandidates.empty())
        {
            result.reasonCode =
                LegacyOneRingReasonCode::NoAdjacentFaceCountMatch;
            return result;
        }
        if (result.extraordinaryCornerCandidates.size() == 2u)
        {
            result.reasonCode =
                LegacyOneRingReasonCode::AmbiguousAdjacentFaceCountMatch;
            return result;
        }
        if (result.extraordinaryCornerCandidates.size() == 1u)
        {
            const int candidate = result.extraordinaryCornerCandidates.front();
            hasCardinalityMismatch = true;
            d4 = face.adjacentVertices[candidate];
            d7 = face.adjacentVertices[(candidate + 1) % 3];
            d8 = face.adjacentVertices[(candidate + 2) % 3];
        }
        else
        {
            // The accepted all-valence-5 fixture makes all three corners match.
            // Preserve the historical first-branch choice and report the
            // aliasing; D5, not WP1.1a, governs quarantining that behavior.
            result.candidateExtraordinaryCorner = 0;
            d4 = face.adjacentVertices[0];
            d7 = face.adjacentVertices[1];
            d8 = face.adjacentVertices[2];
        }
    }

    const Matrix coord4 = vertices[face.adjacentVertices[0]].coord;
    const Matrix coord7 = vertices[face.adjacentVertices[1]].coord;
    const Matrix coord8 = vertices[face.adjacentVertices[2]].coord;
    const Matrix center = 1.0 / 3.0 * (coord4 + coord7 + coord8);
    result.orientedFaceVertices = face.adjacentVertices;
    if (dot_col(center, cross_col(coord7 - coord4, coord8 - coord4)) < 0)
    {
        std::swap(d7, d8);
        result.orientedFaceVertices = {d4, d7, d8};
    }

    std::array<int, 12> staged{{-1, -1, -1, -1, -1, -1,
                                -1, -1, -1, -1, -1, -1}};
    staged[3] = d4;
    staged[6] = d7;
    staged[7] = d8;
    const auto assign_opposite = [this, &result, &staged](
                                     const int slot,
                                     const int node1,
                                     const int node2,
                                     const int node3) {
        const OppositeNodeSearchResult search =
            find_unique_opposite_node_index(vertices, node1, node2, node3);
        switch (search.state)
        {
        case OppositeNodeSearchState::Unique:
            staged[slot] = search.vertex;
            return true;
        case OppositeNodeSearchState::Missing:
            result.reasonCode = LegacyOneRingReasonCode::OppositeNodeMissing;
            return false;
        case OppositeNodeSearchState::Ambiguous:
            result.reasonCode = LegacyOneRingReasonCode::OppositeNodeAmbiguous;
            return false;
        case OppositeNodeSearchState::InvalidVertexIndex:
            result.reasonCode =
                LegacyOneRingReasonCode::InvalidAdjacentVertexIndex;
            return false;
        }
        result.reasonCode = LegacyOneRingReasonCode::OppositeNodeMissing;
        return false;
    };

    if (!assign_opposite(2, staged[3], staged[6], staged[7]) ||
        !assign_opposite(10, staged[6], staged[7], staged[3]) ||
        !assign_opposite(4, staged[3], staged[7], staged[6]) ||
        !assign_opposite(0, staged[2], staged[3], staged[6]) ||
        !assign_opposite(1, staged[3], staged[4], staged[7]) ||
        !assign_opposite(5, staged[2], staged[6], staged[3]) ||
        !assign_opposite(8, staged[7], staged[4], staged[3]) ||
        !assign_opposite(9, staged[6], staged[10], staged[7]) ||
        !assign_opposite(11, staged[7], staged[10], staged[6]))
    {
        result.orientedFaceVertices.clear();
        return result;
    }

    if (regular)
    {
        result.assembledOneRing.assign(staged.begin(), staged.end());
        result.reasonCode = LegacyOneRingReasonCode::ReadyRegular;
    }
    else
    {
        result.assembledOneRing.assign(staged.begin() + 1, staged.end());
        result.reasonCode = hasCardinalityMismatch
                                ? LegacyOneRingReasonCode::
                                      AdjacentVertexFaceCardinalityMismatch
                                : LegacyOneRingReasonCode::
                                      ReadyAllValenceFiveAliased;
    }

    for (std::size_t index = 0; index < result.assembledOneRing.size(); ++index)
    {
        const int source = result.assembledOneRing[index];
        const bool seenEarlier =
            std::find(result.assembledOneRing.begin(),
                      result.assembledOneRing.begin() + index,
                      source) != result.assembledOneRing.begin() + index;
        const bool alreadyReported =
            std::find(result.duplicateSourceIds.begin(),
                      result.duplicateSourceIds.end(),
                      source) != result.duplicateSourceIds.end();
        if (seenEarlier && !alreadyReported)
        {
            result.duplicateSourceIds.push_back(source);
        }
    }
    result.everyRequiredIndexAssignedUniquely = true;
    return result;
}

// Stage every supported face first. A malformed legacy candidate therefore
// rejects before any face orientation or one-ring publication.
void Mesh::set_one_ring_vertices_sorted()
{
    std::vector<LegacyOneRingClassification> classifications;
    classifications.reserve(faces.size());
    for (const Face &face : faces)
    {
        classifications.push_back(classify_legacy_one_ring(face));
        const LegacyOneRingClassification &classification =
            classifications.back();
        if (is_legacy_one_ring_rejection(classification.reasonCode))
        {
            std::ostringstream message;
            message << "Legacy one-ring setup rejected face " << face.index
                    << ": "
                    << legacy_one_ring_reason_code_name(classification.reasonCode);
            throw std::runtime_error(message.str());
        }
    }

    for (std::size_t faceIndex = 0; faceIndex < faces.size(); ++faceIndex)
    {
        LegacyOneRingClassification &classification = classifications[faceIndex];
        if (classification.reasonCode != LegacyOneRingReasonCode::ReadyRegular &&
            classification.reasonCode !=
                LegacyOneRingReasonCode::ReadyAllValenceFiveAliased &&
            classification.reasonCode !=
                LegacyOneRingReasonCode::AdjacentVertexFaceCardinalityMismatch)
        {
            continue;
        }
        faces[faceIndex].adjacentVertices.swap(
            classification.orientedFaceVertices);
        faces[faceIndex].oneRingVertices.swap(classification.assembledOneRing);
    }

    if (param.VERBOSE_MODE)
    {
        std::cout << "[Mesh::set_one_ring_vertices_sorted] One ring vertices set."
                  << std::endl;
    }
}
