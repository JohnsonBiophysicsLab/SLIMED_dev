#pragma once

#include <algorithm>
#include <array>
#include <cerrno>
#include <cfenv>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <queue>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace b2fixture {

struct Mesh {
    std::vector<std::array<double, 3> > vertices;
    std::vector<std::array<int, 3> > faces;
    std::vector<int> valences;
};

inline std::vector<std::string> split_csv_line(std::string const &line) {
    std::vector<std::string> values;
    std::stringstream stream(line);
    std::string value;
    while (std::getline(stream, value, ',')) {
        values.push_back(value);
    }
    if (!line.empty() && line[line.size() - 1] == ',') {
        values.push_back("");
    }
    return values;
}

inline double parse_binary64(std::string const &text) {
    errno = 0;
    char *end = nullptr;
    double const value = std::strtod(text.c_str(), &end);
    if (errno == ERANGE || end != text.c_str() + text.size() || !std::isfinite(value)) {
        throw std::runtime_error("invalid finite binary64 fixture coordinate");
    }
    return value;
}

inline int parse_int32(std::string const &text) {
    errno = 0;
    char *end = nullptr;
    long const value = std::strtol(text.c_str(), &end, 10);
    if (errno == ERANGE || end != text.c_str() + text.size() ||
        value < 0 || value > 2147483647L) {
        throw std::runtime_error("invalid nonnegative int32 fixture index");
    }
    return static_cast<int>(value);
}

inline Mesh read_mesh(std::string const &directory) {
    Mesh mesh;
    std::ifstream vertices((directory + "/vertices.csv").c_str());
    std::ifstream faces((directory + "/faces.csv").c_str());
    if (!vertices || !faces) {
        throw std::runtime_error("fixture CSV pair is unavailable");
    }
    std::string line;
    while (std::getline(vertices, line)) {
        std::vector<std::string> const fields = split_csv_line(line);
        if (fields.size() != 3) {
            throw std::runtime_error("fixture vertex row is not xyz");
        }
        mesh.vertices.push_back({{parse_binary64(fields[0]), parse_binary64(fields[1]),
                                  parse_binary64(fields[2])}});
    }
    while (std::getline(faces, line)) {
        std::vector<std::string> const fields = split_csv_line(line);
        if (fields.size() != 3) {
            throw std::runtime_error("fixture face row is not triangular");
        }
        mesh.faces.push_back({{parse_int32(fields[0]), parse_int32(fields[1]),
                               parse_int32(fields[2])}});
    }
    if (!vertices.eof() || !faces.eof() || mesh.vertices.empty() || mesh.faces.empty()) {
        throw std::runtime_error("fixture CSV read failed or is empty");
    }
    return mesh;
}

inline std::uint64_t bits(double value) {
    std::uint64_t result = 0;
    static_assert(sizeof(result) == sizeof(value), "binary64 size drift");
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

inline void apply_mutation(Mesh &mesh, std::string const &mutation) {
    if (mutation.empty() || mutation == "none") {
        return;
    }
    if (mutation == "coordinate_perturbation_v1") {
        if (mesh.vertices.size() <= 1 || std::fegetround() != FE_TONEAREST) {
            throw std::runtime_error("coordinate mutation requires vertex row 1 and FE_TONEAREST");
        }
        std::array<std::uint64_t, 3> const expected = {{
            UINT64_C(0x3ff2b851eb851eb8), UINT64_C(0xbfe0cffc0ea99f27),
            UINT64_C(0x3fc0a3d70a3d70a4)}};
        std::array<std::uint64_t, 3> const output = {{
            UINT64_C(0x3ff2c851eb851eb8), UINT64_C(0xbfe0dffc0ea99f27),
            UINT64_C(0x3fc0c3d70a3d70a4)}};
        std::array<double, 3> const delta = {{0x1.0p-8, -0x1.0p-9, 0x1.0p-10}};
        for (int axis = 0; axis < 3; ++axis) {
            if (bits(mesh.vertices[1][axis]) != expected[axis]) {
                throw std::runtime_error("coordinate mutation input bits drift");
            }
            mesh.vertices[1][axis] = mesh.vertices[1][axis] + delta[axis];
            if (bits(mesh.vertices[1][axis]) != output[axis]) {
                throw std::runtime_error("coordinate mutation output bits drift");
            }
        }
        return;
    }
    if (mutation == "reverse_face_zero_v1") {
        std::swap(mesh.faces.at(0)[1], mesh.faces.at(0)[2]);
        return;
    }
    if (mutation == "delete_face_zero_v1") {
        mesh.faces.erase(mesh.faces.begin());
        return;
    }
    if (mutation == "append_face_zero_v1") {
        mesh.faces.push_back(mesh.faces.at(0));
        return;
    }
    throw std::runtime_error("unknown frozen fixture mutation");
}

inline std::pair<int, int> edge_key(int a, int b) {
    return a < b ? std::make_pair(a, b) : std::make_pair(b, a);
}

inline void validate_closed_oriented_two_manifold(Mesh &mesh) {
    std::set<std::array<int, 3> > duplicate_keys;
    std::map<std::pair<int, int>, std::vector<std::pair<int, int> > > edges;
    std::vector<std::set<int> > neighbors(mesh.vertices.size());
    std::vector<std::map<int, std::set<int> > > vertex_links(mesh.vertices.size());
    std::vector<int> referenced(mesh.vertices.size(), 0);
    for (std::size_t face_index = 0; face_index < mesh.faces.size(); ++face_index) {
        std::array<int, 3> const &face = mesh.faces[face_index];
        for (int corner = 0; corner < 3; ++corner) {
            if (face[corner] < 0 || static_cast<std::size_t>(face[corner]) >= mesh.vertices.size() ||
                face[corner] == face[(corner + 1) % 3]) {
                throw std::runtime_error("D2_INVALID_FACE_INDEX_OR_DEGENERACY");
            }
            referenced[static_cast<std::size_t>(face[corner])] = 1;
            int const a = face[corner];
            int const b = face[(corner + 1) % 3];
            edges[edge_key(a, b)].push_back(std::make_pair(a, b));
            neighbors[static_cast<std::size_t>(a)].insert(b);
            neighbors[static_cast<std::size_t>(b)].insert(a);
        }
        std::array<int, 3> sorted = face;
        std::sort(sorted.begin(), sorted.end());
        if (!duplicate_keys.insert(sorted).second) {
            throw std::runtime_error("D2_DUPLICATE_FACE");
        }
        for (int corner = 0; corner < 3; ++corner) {
            int const vertex = face[corner];
            int const previous = face[(corner + 2) % 3];
            int const next = face[(corner + 1) % 3];
            vertex_links[static_cast<std::size_t>(vertex)][previous].insert(next);
            vertex_links[static_cast<std::size_t>(vertex)][next].insert(previous);
        }
    }
    for (std::size_t index = 0; index < referenced.size(); ++index) {
        if (!referenced[index]) {
            throw std::runtime_error("D2_UNREFERENCED_VERTEX");
        }
    }
    for (std::map<std::pair<int, int>, std::vector<std::pair<int, int> > >::const_iterator
             edge = edges.begin(); edge != edges.end(); ++edge) {
        if (edge->second.size() != 2) {
            throw std::runtime_error("D2_NOT_CLOSED_TWO_FACE_EDGE_MANIFOLD");
        }
        if (edge->second[0].first != edge->second[1].second ||
            edge->second[0].second != edge->second[1].first) {
            throw std::runtime_error("D2_INCONSISTENT_ORIENTATION");
        }
    }
    for (std::size_t vertex = 0; vertex < vertex_links.size(); ++vertex) {
        std::map<int, std::set<int> > const &link = vertex_links[vertex];
        if (link.size() != neighbors[vertex].size() || link.size() < 3) {
            throw std::runtime_error("D2_INVALID_CLOSED_VERTEX_LINK");
        }
        for (std::map<int, std::set<int> >::const_iterator item = link.begin();
             item != link.end(); ++item) {
            if (item->second.size() != 2) {
                throw std::runtime_error("D2_INVALID_CLOSED_VERTEX_LINK");
            }
        }
        std::set<int> link_visited;
        std::queue<int> link_pending;
        link_pending.push(link.begin()->first);
        link_visited.insert(link.begin()->first);
        while (!link_pending.empty()) {
            int const current = link_pending.front();
            link_pending.pop();
            std::set<int> const &adjacent = link.find(current)->second;
            for (std::set<int>::const_iterator next = adjacent.begin();
                 next != adjacent.end(); ++next) {
                if (link_visited.insert(*next).second) link_pending.push(*next);
            }
        }
        if (link_visited.size() != link.size()) {
            throw std::runtime_error("D2_INVALID_CLOSED_VERTEX_LINK");
        }
    }
    std::vector<int> visited(mesh.vertices.size(), 0);
    std::queue<int> pending;
    pending.push(0);
    visited[0] = 1;
    while (!pending.empty()) {
        int const vertex = pending.front();
        pending.pop();
        for (std::set<int>::const_iterator next = neighbors[static_cast<std::size_t>(vertex)].begin();
             next != neighbors[static_cast<std::size_t>(vertex)].end(); ++next) {
            if (!visited[static_cast<std::size_t>(*next)]) {
                visited[static_cast<std::size_t>(*next)] = 1;
                pending.push(*next);
            }
        }
    }
    for (std::size_t index = 0; index < visited.size(); ++index) {
        if (!visited[index]) {
            throw std::runtime_error("D2_DISCONNECTED_SURFACE");
        }
    }
    mesh.valences.resize(mesh.vertices.size());
    for (std::size_t index = 0; index < neighbors.size(); ++index) {
        mesh.valences[index] = static_cast<int>(neighbors[index].size());
        if (mesh.valences[index] < 3) {
            throw std::runtime_error("D2_INVALID_CLOSED_VERTEX_LINK");
        }
    }
}

}  // namespace b2fixture
