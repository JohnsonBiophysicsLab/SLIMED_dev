#pragma once

#include "mpfr_interval.hpp"

#include <algorithm>
#include <cstddef>
#include <numeric>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace b2stam {

using b2interval::MpfrInterval;
using Vector = std::vector<MpfrInterval>;
using Matrix = std::vector<Vector>;

inline Matrix zero_matrix(std::size_t rows, std::size_t columns) {
    return Matrix(rows, Vector(columns, MpfrInterval(0)));
}

inline Matrix identity_matrix(std::size_t size) {
    Matrix result = zero_matrix(size, size);
    for (std::size_t index = 0; index < size; ++index) {
        result[index][index] = MpfrInterval(1);
    }
    return result;
}

inline Matrix multiply(Matrix const &left, Matrix const &right) {
    if (left.empty() || right.empty() || left.front().size() != right.size()) {
        throw std::runtime_error("interval matrix multiply shape mismatch");
    }
    Matrix result = zero_matrix(left.size(), right.front().size());
    for (std::size_t row = 0; row < left.size(); ++row) {
        if (left[row].size() != right.size()) {
            throw std::runtime_error("ragged left interval matrix");
        }
        for (std::size_t inner = 0; inner < right.size(); ++inner) {
            if (right[inner].size() != right.front().size()) {
                throw std::runtime_error("ragged right interval matrix");
            }
            for (std::size_t column = 0; column < right.front().size(); ++column) {
                result[row][column] = b2interval::add(
                    result[row][column],
                    b2interval::multiply(left[row][inner], right[inner][column]));
            }
        }
    }
    return result;
}

inline Matrix subtract(Matrix const &left, Matrix const &right) {
    if (left.size() != right.size() || left.empty() ||
        left.front().size() != right.front().size()) {
        throw std::runtime_error("interval matrix subtract shape mismatch");
    }
    Matrix result = left;
    for (std::size_t row = 0; row < left.size(); ++row) {
        if (left[row].size() != left.front().size() ||
            right[row].size() != right.front().size()) {
            throw std::runtime_error("ragged interval matrix subtraction");
        }
        for (std::size_t column = 0; column < left.front().size(); ++column) {
            result[row][column] = b2interval::subtract(
                left[row][column], right[row][column]);
        }
    }
    return result;
}

inline Matrix transpose(Matrix const &value) {
    if (value.empty()) {
        throw std::runtime_error("empty interval matrix transpose");
    }
    Matrix result = zero_matrix(value.front().size(), value.size());
    for (std::size_t row = 0; row < value.size(); ++row) {
        if (value[row].size() != value.front().size()) {
            throw std::runtime_error("ragged interval matrix transpose");
        }
        for (std::size_t column = 0; column < value.front().size(); ++column) {
            result[column][row] = value[row][column];
        }
    }
    return result;
}

inline bool certified_nonzero(MpfrInterval const &value) {
    return mpfr_sgn(value.lo()) > 0 || mpfr_sgn(value.hi()) < 0;
}

inline Matrix interval_inverse(Matrix value) {
    if (value.empty() || value.size() != value.front().size()) {
        throw std::runtime_error("interval inverse requires square matrix");
    }
    std::size_t const size = value.size();
    Matrix inverse = identity_matrix(size);
    for (std::size_t column = 0; column < size; ++column) {
        std::size_t pivot = column;
        while (pivot < size && !certified_nonzero(value[pivot][column])) {
            ++pivot;
        }
        if (pivot == size) {
            throw std::runtime_error("interval eigenbasis pivot uncertified");
        }
        if (pivot != column) {
            std::swap(value[pivot], value[column]);
            std::swap(inverse[pivot], inverse[column]);
        }
        MpfrInterval const divisor = value[column][column];
        for (std::size_t index = 0; index < size; ++index) {
            value[column][index] = b2interval::divide(
                value[column][index], divisor);
            inverse[column][index] = b2interval::divide(
                inverse[column][index], divisor);
        }
        for (std::size_t row = 0; row < size; ++row) {
            if (row == column) {
                continue;
            }
            MpfrInterval const factor = value[row][column];
            for (std::size_t index = 0; index < size; ++index) {
                value[row][index] = b2interval::subtract(
                    value[row][index],
                    b2interval::multiply(factor, value[column][index]));
                inverse[row][index] = b2interval::subtract(
                    inverse[row][index],
                    b2interval::multiply(factor, inverse[column][index]));
            }
        }
    }
    return inverse;
}

inline Matrix midpoint_matrix(Matrix const &value) {
    Matrix result = value;
    for (std::size_t row = 0; row < value.size(); ++row) {
        for (std::size_t column = 0; column < value[row].size(); ++column) {
            result[row][column] = value[row][column].midpoint();
        }
    }
    return result;
}

inline Matrix krawczyk_inverse(Matrix const &value) {
    if (value.empty() || value.size() != value.front().size()) {
        throw std::runtime_error("Krawczyk inverse requires square matrix");
    }
    std::size_t const size = value.size();
    Matrix approximate = midpoint_matrix(interval_inverse(midpoint_matrix(value)));
    Matrix residual_operator = subtract(
        identity_matrix(size), multiply(approximate, value));
    Matrix certified = zero_matrix(size, size);
    MpfrInterval const symmetric_delta =
        MpfrInterval(0).expanded("1e-120");
    for (std::size_t column = 0; column < size; ++column) {
        Matrix center = zero_matrix(size, 1);
        Matrix box_delta = zero_matrix(size, 1);
        Matrix right_hand_side = zero_matrix(size, 1);
        for (std::size_t row = 0; row < size; ++row) {
            center[row][0] = approximate[row][column];
            box_delta[row][0] = symmetric_delta;
        }
        right_hand_side[column][0] = MpfrInterval(1);
        Matrix equation_residual = subtract(
            multiply(value, center), right_hand_side);
        Matrix base = subtract(
            center, multiply(approximate, equation_residual));
        Matrix image = multiply(residual_operator, box_delta);
        Matrix krawczyk = zero_matrix(size, 1);
        for (std::size_t row = 0; row < size; ++row) {
            krawczyk[row][0] = b2interval::add(base[row][0], image[row][0]);
            MpfrInterval outer = center[row][0].expanded("1e-120");
            if (!b2interval::strict_interior(krawczyk[row][0], outer)) {
                throw std::runtime_error("interval Krawczyk inclusion failed");
            }
            certified[row][column] = outer;
        }
    }
    return certified;
}

inline MpfrInterval infinity_norm(Matrix const &value) {
    MpfrInterval maximum(0);
    for (Vector const &row : value) {
        MpfrInterval sum(0);
        for (MpfrInterval const &entry : row) {
            sum = b2interval::add(sum, b2interval::absolute(entry));
        }
        if (mpfr_greater_p(sum.hi(), maximum.hi())) {
            maximum = sum;
        }
    }
    return maximum;
}

inline bool normalized_eigen_residual(
        Matrix const &subdivision, Matrix const &vectors,
        Matrix const &canonical, Matrix const &residual,
        char const *maximum) {
    (void)canonical;
    MpfrInterval const vector_norm = infinity_norm(vectors);
    MpfrInterval const operator_scale = b2interval::multiply(
        infinity_norm(subdivision), vector_norm);
    MpfrInterval denominator(1);
    if (mpfr_greater_p(operator_scale.lo(), denominator.hi())) {
        denominator = MpfrInterval::point(operator_scale.lo());
    }
    if (!mpfr_greater_p(denominator.lo(), MpfrInterval(0).hi())) {
        throw std::runtime_error("normalized eigen residual scale uncertified");
    }
    MpfrInterval const normalized = b2interval::divide(
        infinity_norm(residual), denominator);
    return b2interval::upper_at_most(normalized, maximum);
}

inline bool residual_contains_zero(Matrix const &residual,
                                   char const *maximum_width) {
    MpfrInterval bound = MpfrInterval::decimal(maximum_width);
    for (Vector const &row : residual) {
        for (MpfrInterval const &entry : row) {
            if (!entry.contains_zero() ||
                mpfr_greater_p(b2interval::absolute(entry).hi(), bound.lo())) {
                return false;
            }
        }
    }
    return true;
}

inline bool exact_same_interval(MpfrInterval const &left,
                                MpfrInterval const &right) {
    return mpfr_equal_p(left.lo(), right.lo()) &&
           mpfr_equal_p(left.hi(), right.hi());
}

inline bool certified_same_value(MpfrInterval const &left,
                                 MpfrInterval const &right) {
    if (exact_same_interval(left, right)) {
        return true;
    }
    return b2interval::upper_at_most(
        b2interval::absolute(b2interval::subtract(left, right)), "1e-150");
}

inline MpfrInterval dot(Vector const &left, Vector const &right) {
    if (left.size() != right.size()) {
        throw std::runtime_error("interval dot shape mismatch");
    }
    MpfrInterval result(0);
    for (std::size_t index = 0; index < left.size(); ++index) {
        result = b2interval::add(
            result, b2interval::multiply(left[index], right[index]));
    }
    return result;
}

inline MpfrInterval euclidean_norm(Vector const &value) {
    MpfrInterval squared(0);
    for (MpfrInterval const &entry : value) {
        squared = b2interval::add(
            squared,
            b2interval::integer_power(b2interval::absolute(entry), 2));
    }
    return b2interval::square_root(squared);
}

inline Vector matrix_column(Matrix const &value, std::size_t column) {
    Vector result(value.size(), MpfrInterval(0));
    for (std::size_t row = 0; row < value.size(); ++row) {
        if (column >= value[row].size()) {
            throw std::runtime_error("interval matrix column outside shape");
        }
        result[row] = value[row][column];
    }
    return result;
}

inline void set_matrix_column(Matrix &value, std::size_t column,
                              Vector const &entries) {
    if (value.size() != entries.size()) {
        throw std::runtime_error("interval matrix column assignment shape mismatch");
    }
    for (std::size_t row = 0; row < value.size(); ++row) {
        if (column >= value[row].size()) {
            throw std::runtime_error("interval matrix column assignment outside shape");
        }
        value[row][column] = entries[row];
    }
}

inline bool certified_norm_exceeds(MpfrInterval const &value,
                                   char const *threshold) {
    MpfrInterval const bound = MpfrInterval::decimal(threshold);
    return mpfr_greater_p(value.lo(), bound.hi());
}

inline std::size_t signed_pivot(Vector const &value) {
    std::vector<MpfrInterval> magnitudes;
    magnitudes.reserve(value.size());
    for (MpfrInterval const &entry : value) {
        magnitudes.push_back(b2interval::absolute(entry));
    }
    for (std::size_t candidate = 0; candidate < value.size(); ++candidate) {
        bool maximum = true;
        for (std::size_t other = 0; other < value.size(); ++other) {
            if (candidate == other) {
                continue;
            }
            MpfrInterval const difference = b2interval::absolute(
                b2interval::subtract(magnitudes[candidate],
                                     magnitudes[other]));
            bool const symmetry_tie_enclosed =
                magnitudes[candidate].contains_zero() ==
                    magnitudes[other].contains_zero() &&
                b2interval::upper_at_most(difference, "1e-100");
            if (exact_same_interval(magnitudes[candidate], magnitudes[other]) ||
                symmetry_tie_enclosed) {
                continue;
            }
            if (!mpfr_greater_p(magnitudes[candidate].lo(),
                                magnitudes[other].hi())) {
                maximum = false;
                break;
            }
        }
        if (maximum) {
            if (!certified_nonzero(value[candidate])) {
                throw std::runtime_error("eigenvector sign pivot contains zero");
            }
            return candidate;
        }
    }
    throw std::runtime_error("eigenvector maximum pivot ordering uncertified");
}

inline bool krawczyk_simple_eigenpair(
        Matrix const &subdivision, MpfrInterval const &eigenvalue,
        Vector const &seed_vector) {
    if (subdivision.empty() || subdivision.size() != seed_vector.size()) {
        throw std::runtime_error("simple eigenpair Krawczyk shape mismatch");
    }
    std::size_t const size = seed_vector.size();
    std::size_t const pivot = signed_pivot(seed_vector);
    Vector normalized(size, MpfrInterval(0));
    for (std::size_t row = 0; row < size; ++row) {
        normalized[row] = b2interval::divide(
            seed_vector[row], seed_vector[pivot]);
    }
    Matrix equation = subdivision;
    for (std::size_t row = 0; row < size; ++row) {
        equation[row][row] = b2interval::subtract(
            equation[row][row], eigenvalue);
    }
    // Replace one redundant eigen equation by the deterministic signed-pivot
    // normalization.  At least one row must give a nonsingular augmented
    // system for a simple eigenvalue.
    for (std::size_t removed = 0; removed < size; ++removed) {
        try {
            Matrix augmented = equation;
            Matrix right = zero_matrix(size, 1);
            for (std::size_t column = 0; column < size; ++column) {
                augmented[removed][column] = MpfrInterval(
                    column == pivot ? 1 : 0);
            }
            right[removed][0] = MpfrInterval(1);
            Matrix approximate_inverse = midpoint_matrix(
                interval_inverse(midpoint_matrix(augmented)));
            Matrix residual_operator = subtract(
                identity_matrix(size),
                multiply(approximate_inverse, augmented));
            Matrix center = zero_matrix(size, 1);
            Matrix box_delta = zero_matrix(size, 1);
            MpfrInterval const delta = MpfrInterval(0).expanded("1e-110");
            for (std::size_t row = 0; row < size; ++row) {
                center[row][0] = normalized[row].midpoint();
                box_delta[row][0] = delta;
            }
            Matrix equation_residual = subtract(
                multiply(augmented, center), right);
            Matrix base = subtract(
                center, multiply(approximate_inverse, equation_residual));
            Matrix image = multiply(residual_operator, box_delta);
            for (std::size_t row = 0; row < size; ++row) {
                MpfrInterval const krawczyk = b2interval::add(
                    base[row][0], image[row][0]);
                if (!b2interval::strict_interior(
                        krawczyk, center[row][0].expanded("1e-110"))) {
                    throw std::runtime_error(
                        "simple eigenpair Krawczyk inclusion failed");
                }
            }
            return true;
        } catch (std::runtime_error const &) {
            // Exhaust the deterministic removed-equation order.
        }
    }
    throw std::runtime_error("simple eigenpair Krawczyk inclusion failed");
}

struct DeterministicBlock {
    Matrix projector;
    std::vector<Vector> vectors;
};

inline DeterministicBlock deterministic_projector_block(
    Matrix const &seed_vectors, std::vector<std::size_t> const &columns) {
    if (seed_vectors.empty() || columns.empty()) {
        throw std::runtime_error("empty repeated eigenspace seed");
    }
    Matrix seed = zero_matrix(seed_vectors.size(), columns.size());
    for (std::size_t block_column = 0; block_column < columns.size();
         ++block_column) {
        set_matrix_column(seed, block_column,
                          matrix_column(seed_vectors, columns[block_column]));
    }
    Matrix gram = multiply(transpose(seed), seed);
    Matrix projector = multiply(
        multiply(seed, krawczyk_inverse(gram)), transpose(seed));

    std::vector<Vector> accepted;
    for (std::size_t source_id = 0;
         source_id < seed_vectors.size() && accepted.size() < columns.size();
         ++source_id) {
        Vector residual = matrix_column(projector, source_id);
        for (Vector const &basis_vector : accepted) {
            MpfrInterval coefficient = dot(basis_vector, residual);
            for (std::size_t row = 0; row < residual.size(); ++row) {
                residual[row] = b2interval::subtract(
                    residual[row],
                    b2interval::multiply(coefficient, basis_vector[row]));
            }
        }
        MpfrInterval norm = euclidean_norm(residual);
        if (!certified_norm_exceeds(norm, "1e-60")) {
            continue;
        }
        for (MpfrInterval &entry : residual) {
            entry = b2interval::divide(entry, norm);
        }
        std::size_t const pivot = signed_pivot(residual);
        if (mpfr_sgn(residual[pivot].hi()) < 0) {
            for (MpfrInterval &entry : residual) {
                entry = b2interval::negate(entry);
            }
        }
        accepted.push_back(std::move(residual));
    }
    if (accepted.size() != columns.size()) {
        throw std::runtime_error("deterministic Gram-Schmidt block is incomplete");
    }

    Matrix orthonormal = zero_matrix(seed_vectors.size(), accepted.size());
    for (std::size_t column = 0; column < accepted.size(); ++column) {
        set_matrix_column(orthonormal, column, accepted[column]);
    }
    Matrix orthonormal_residual = subtract(
        multiply(transpose(orthonormal), orthonormal),
        identity_matrix(accepted.size()));
    if (!residual_contains_zero(orthonormal_residual, "1e-70")) {
        throw std::runtime_error("deterministic Gram-Schmidt residual failed");
    }
    Matrix projector_residual = subtract(
        projector, multiply(orthonormal, transpose(orthonormal)));
    if (!residual_contains_zero(projector_residual, "1e-70")) {
        throw std::runtime_error("spectral projector reconstruction failed");
    }
    return {projector, accepted};
}

inline MpfrInterval loop_tangent_eigenvalue(unsigned valence,
                                             unsigned frequency) {
    return b2interval::add(
        MpfrInterval::rational(3, 8),
        b2interval::multiply(
            MpfrInterval::rational(1, 4),
            b2interval::loop_angle_cosine(valence, frequency)));
}

inline Matrix stock_subdivision_matrix(unsigned valence) {
    if (valence < 3 || valence > 50) {
        throw std::runtime_error("primary stock matrix valence outside certified range");
    }
    std::size_t const size = valence + 6;
    Matrix result = zero_matrix(size, size);
    if (valence == 3) {
        long const numerators[9][9] = {
            {7, 3, 3, 3, 0, 0, 0, 0, 0},
            {6, 6, 2, 2, 0, 0, 0, 0, 0},
            {6, 2, 6, 2, 0, 0, 0, 0, 0},
            {6, 2, 2, 6, 0, 0, 0, 0, 0},
            {2, 6, 0, 6, 2, 0, 0, 0, 0},
            {1, 10, 1, 1, 1, 1, 1, 0, 0},
            {2, 6, 6, 0, 0, 0, 2, 0, 0},
            {1, 1, 1, 10, 1, 0, 0, 1, 1},
            {2, 0, 6, 6, 0, 0, 0, 0, 2},
        };
        for (std::size_t row = 0; row < 9; ++row) {
            for (std::size_t column = 0; column < 9; ++column) {
                result[row][column] = MpfrInterval::rational(
                    numerators[row][column], 16);
            }
        }
        return result;
    }
    MpfrInterval tangent = loop_tangent_eigenvalue(valence, 1);
    MpfrInterval beta = b2interval::divide(
        b2interval::subtract(MpfrInterval::rational(5, 8),
                             b2interval::multiply(tangent, tangent)),
        MpfrInterval(static_cast<long>(valence)));
    result[0][0] = b2interval::subtract(
        MpfrInterval(1),
        b2interval::multiply(MpfrInterval(static_cast<long>(valence)), beta));
    for (unsigned ring = 0; ring < valence; ++ring) {
        result[0][1 + ring] = beta;
        std::size_t const row = 1 + ring;
        result[row][0] = MpfrInterval::rational(3, 8);
        result[row][1 + ring] = MpfrInterval::rational(3, 8);
        result[row][1 + ((ring + valence - 1) % valence)] =
            MpfrInterval::rational(1, 8);
        result[row][1 + ((ring + 1) % valence)] =
            MpfrInterval::rational(1, 8);
    }
    std::size_t const outer = 1 + valence;
    result[outer][0] = MpfrInterval::rational(1, 8);
    result[outer][1] = MpfrInterval::rational(3, 8);
    result[outer][valence] = MpfrInterval::rational(3, 8);
    result[outer][outer] = MpfrInterval::rational(1, 8);

    result[outer + 1][0] = MpfrInterval::rational(1, 16);
    result[outer + 1][1] = MpfrInterval::rational(10, 16);
    result[outer + 1][2] = MpfrInterval::rational(1, 16);
    result[outer + 1][valence] = MpfrInterval::rational(1, 16);
    result[outer + 1][outer] = MpfrInterval::rational(1, 16);
    result[outer + 1][outer + 1] = MpfrInterval::rational(1, 16);
    result[outer + 1][outer + 2] = MpfrInterval::rational(1, 16);

    result[outer + 2][0] = MpfrInterval::rational(1, 8);
    result[outer + 2][1] = MpfrInterval::rational(3, 8);
    result[outer + 2][2] = MpfrInterval::rational(3, 8);
    result[outer + 2][outer + 2] = MpfrInterval::rational(1, 8);

    result[outer + 3][0] = MpfrInterval::rational(1, 16);
    result[outer + 3][1] = MpfrInterval::rational(1, 16);
    result[outer + 3][valence - 1] = MpfrInterval::rational(1, 16);
    result[outer + 3][valence] = MpfrInterval::rational(10, 16);
    result[outer + 3][outer] = MpfrInterval::rational(1, 16);
    result[outer + 3][outer + 3] = MpfrInterval::rational(1, 16);
    result[outer + 3][outer + 4] = MpfrInterval::rational(1, 16);

    result[outer + 4][0] = MpfrInterval::rational(1, 8);
    result[outer + 4][valence - 1] = MpfrInterval::rational(3, 8);
    result[outer + 4][valence] = MpfrInterval::rational(3, 8);
    result[outer + 4][outer + 4] = MpfrInterval::rational(1, 8);
    return result;
}

inline void complete_outer(Vector &column, MpfrInterval const &eigenvalue,
                           unsigned valence) {
    std::size_t const outer = 1 + valence;
    MpfrInterval eighth = MpfrInterval::rational(1, 8);
    MpfrInterval sixteenth = MpfrInterval::rational(1, 16);
    auto edge_value = [&](MpfrInterval const &left,
                          MpfrInterval const &right) {
        MpfrInterval numerator = b2interval::add(
            b2interval::multiply(eighth, column[0]),
            b2interval::multiply(MpfrInterval::rational(3, 8),
                                 b2interval::add(left, right)));
        return b2interval::divide(
            numerator, b2interval::subtract(eigenvalue, eighth));
    };
    column[outer] = edge_value(column[1], column[valence]);
    column[outer + 2] = edge_value(column[1], column[2]);
    column[outer + 4] = edge_value(column[valence - 1], column[valence]);
    MpfrInterval left_sum = column[0];
    left_sum = b2interval::add(
        left_sum,
        b2interval::multiply(MpfrInterval(10), column[1]));
    left_sum = b2interval::add(left_sum, column[2]);
    left_sum = b2interval::add(left_sum, column[valence]);
    left_sum = b2interval::add(left_sum, column[outer]);
    left_sum = b2interval::add(left_sum, column[outer + 2]);
    column[outer + 1] = b2interval::divide(
        b2interval::multiply(sixteenth, left_sum),
        b2interval::subtract(eigenvalue, sixteenth));
    MpfrInterval right_sum = column[0];
    right_sum = b2interval::add(right_sum, column[1]);
    right_sum = b2interval::add(right_sum, column[valence - 1]);
    right_sum = b2interval::add(
        right_sum,
        b2interval::multiply(MpfrInterval(10), column[valence]));
    right_sum = b2interval::add(right_sum, column[outer]);
    right_sum = b2interval::add(right_sum, column[outer + 4]);
    column[outer + 3] = b2interval::divide(
        b2interval::multiply(sixteenth, right_sum),
        b2interval::subtract(eigenvalue, sixteenth));
}

struct Eigenbasis {
    Matrix vectors;
    std::vector<MpfrInterval> eigenvalues;
    Matrix canonical;
};

inline Eigenbasis analytic_eigenbasis(unsigned valence) {
    if (valence < 3 || valence > 50) {
        throw std::runtime_error("analytic eigenbasis valence outside certified range");
    }
    std::size_t const size = valence + 6;
    std::vector<Vector> columns;
    std::vector<MpfrInterval> eigenvalues;
    auto append = [&](Vector const &column, MpfrInterval const &eigenvalue) {
        columns.push_back(column);
        eigenvalues.push_back(eigenvalue);
    };

    if (valence == 3) {
        struct RationalEntry { long numerator; unsigned denominator; };
        // Stam, Appendix C: the columns of this exact rational matrix are a
        // Jordan basis.  In particular, columns 7 and 8 (zero based) form the
        // non-trivial 1/16 block; they must not be treated as independent
        // eigenvectors.
        RationalEntry const raw_rows[9][9] = {
            {{1,1},{0,1},{0,1},{0,1},{0,1},{0,1},{0,1},{0,1},{33,1}},
            {{1,1},{0,1},{1,1},{0,1},{0,1},{0,1},{0,1},{0,1},{-22,1}},
            {{1,1},{-1,1},{-1,1},{0,1},{0,1},{0,1},{0,1},{0,1},{-22,1}},
            {{1,1},{1,1},{0,1},{0,1},{0,1},{0,1},{0,1},{0,1},{-22,1}},
            {{1,1},{3,1},{3,1},{1,1},{-1,1},{0,1},{0,1},{0,1},{198,1}},
            {{1,1},{0,1},{4,1},{1,1},{0,1},{0,1},{0,1},{165,16},{473,1}},
            {{1,1},{-3,1},{0,1},{0,1},{1,1},{0,1},{0,1},{0,1},{198,1}},
            {{1,1},{4,1},{0,1},{0,1},{0,1},{1,1},{1,1},{165,16},{438,1}},
            {{1,1},{0,1},{-3,1},{-1,1},{1,1},{1,1},{0,1},{0,1},{198,1}},
        };
        MpfrInterval const raw_values[9] = {
            MpfrInterval(1),
            MpfrInterval::rational(1,4), MpfrInterval::rational(1,4),
            MpfrInterval::rational(1,8), MpfrInterval::rational(1,8),
            MpfrInterval::rational(1,8), MpfrInterval::rational(1,16),
            MpfrInterval::rational(1,16), MpfrInterval::rational(1,16),
        };
        Matrix vectors = zero_matrix(9, 9);
        for (std::size_t row = 0; row < 9; ++row) {
            for (std::size_t column = 0; column < 9; ++column) {
                vectors[row][column] = MpfrInterval::rational(
                    raw_rows[row][column].numerator,
                    raw_rows[row][column].denominator);
            }
        }
        Matrix canonical = zero_matrix(9, 9);
        for (std::size_t index = 0; index < 9; ++index) {
            eigenvalues.push_back(raw_values[index]);
            canonical[index][index] = raw_values[index];
        }
        canonical[7][8] = MpfrInterval(1);
        return {vectors, eigenvalues, canonical};
    }

    append(Vector(size, MpfrInterval(1)), MpfrInterval(1));

    for (unsigned frequency = 1; frequency <= (valence - 1) / 2; ++frequency) {
        MpfrInterval eigenvalue = loop_tangent_eigenvalue(valence, frequency);
        Vector cosine(size, MpfrInterval(0));
        Vector sine(size, MpfrInterval(0));
        for (unsigned ring = 0; ring < valence; ++ring) {
            unsigned const phase = (frequency * ring) % valence;
            cosine[1 + ring] = b2interval::loop_angle_cosine(valence, phase);
            sine[1 + ring] = b2interval::loop_angle_sine(valence, phase);
        }
        complete_outer(cosine, eigenvalue, valence);
        complete_outer(sine, eigenvalue, valence);
        append(cosine, eigenvalue);
        append(sine, eigenvalue);
    }

    MpfrInterval tangent = loop_tangent_eigenvalue(valence, 1);
    MpfrInterval radial_eigenvalue = b2interval::multiply(tangent, tangent);
    Vector radial(size, MpfrInterval(0));
    radial[0] = b2interval::multiply(
        MpfrInterval::rational(8, 3),
        b2interval::subtract(radial_eigenvalue,
                             MpfrInterval::rational(5, 8)));
    for (unsigned ring = 0; ring < valence; ++ring) {
        radial[1 + ring] = MpfrInterval(1);
    }
    complete_outer(radial, radial_eigenvalue, valence);
    append(radial, radial_eigenvalue);

    if ((valence & 1U) == 0) {
        Vector alternating(size, MpfrInterval(0));
        for (unsigned ring = 0; ring < valence; ++ring) {
            alternating[1 + ring] = MpfrInterval((ring & 1U) ? -1 : 1);
        }
        std::size_t const outer = 1 + valence;
        alternating[outer + 1] = MpfrInterval(8);
        alternating[outer + 3] = MpfrInterval(-8);
        append(alternating, MpfrInterval::rational(1, 8));
    }

    std::size_t const outer = 1 + valence;
    for (unsigned mode = 0; mode < 3; ++mode) {
        Vector fixed(size, MpfrInterval(0));
        fixed[outer + 2 * mode] = MpfrInterval(1);
        fixed[outer + 1] = MpfrInterval(mode < 2 ? 1 : 0);
        fixed[outer + 3] = MpfrInterval(mode == 0 || mode == 2 ? 1 : 0);
        append(fixed, MpfrInterval::rational(1, 8));
    }
    for (unsigned mode = 0; mode < 2; ++mode) {
        Vector fixed(size, MpfrInterval(0));
        fixed[outer + 1 + 2 * mode] = MpfrInterval(1);
        append(fixed, MpfrInterval::rational(1, 16));
    }
    if (columns.size() != size) {
        throw std::runtime_error("analytic eigenbasis cardinality mismatch");
    }
    Matrix vectors = zero_matrix(size, size);
    for (std::size_t column = 0; column < size; ++column) {
        for (std::size_t row = 0; row < size; ++row) {
            vectors[row][column] = columns[column][row];
        }
    }
    Matrix canonical = zero_matrix(size, size);
    for (std::size_t index = 0; index < size; ++index) {
        canonical[index][index] = eigenvalues[index];
    }
    return {vectors, eigenvalues, canonical};
}

inline Eigenbasis deterministic_eigenbasis(unsigned valence) {
    Eigenbasis seed = analytic_eigenbasis(valence);
    if (valence == 3) {
        // Appendix C fixes an exact rational Jordan basis.  The non-trivial
        // generalized block cannot be replaced by independently normalized
        // eigenvectors; its separate block-power certificate is mandatory.
        return seed;
    }

    std::vector<std::size_t> order(seed.eigenvalues.size());
    std::iota(order.begin(), order.end(), 0);
    std::stable_sort(order.begin(), order.end(),
                     [&](std::size_t left, std::size_t right) {
        MpfrInterval const &a = seed.eigenvalues[left];
        MpfrInterval const &b = seed.eigenvalues[right];
        if (certified_same_value(a, b)) {
            return false;
        }
        if (mpfr_greater_p(a.lo(), b.hi())) {
            return true;
        }
        if (mpfr_greater_p(b.lo(), a.hi())) {
            return false;
        }
        throw std::runtime_error("eigenvalue block ordering uncertified");
    });

    Matrix vectors = zero_matrix(seed.vectors.size(), seed.vectors.size());
    std::vector<MpfrInterval> eigenvalues;
    std::size_t output_column = 0;
    for (std::size_t begin = 0; begin < order.size();) {
        std::size_t end = begin + 1;
        while (end < order.size() &&
               certified_same_value(seed.eigenvalues[order[begin]],
                                    seed.eigenvalues[order[end]])) {
            ++end;
        }
        std::vector<std::size_t> block_columns(order.begin() + begin,
                                               order.begin() + end);
        DeterministicBlock block;
        try {
            block = deterministic_projector_block(seed.vectors, block_columns);
        } catch (std::runtime_error const &error) {
            throw std::runtime_error(
                std::string("valence ") + std::to_string(valence) +
                " eigenspace dimension " +
                std::to_string(block_columns.size()) + ": " + error.what());
        }
        for (Vector const &vector : block.vectors) {
            set_matrix_column(vectors, output_column++, vector);
            eigenvalues.push_back(seed.eigenvalues[order[begin]]);
        }
        begin = end;
    }
    if (output_column != seed.vectors.size()) {
        throw std::runtime_error("deterministic eigenbasis cardinality mismatch");
    }
    Matrix canonical = zero_matrix(eigenvalues.size(), eigenvalues.size());
    for (std::size_t index = 0; index < eigenvalues.size(); ++index) {
        canonical[index][index] = eigenvalues[index];
    }
    return {vectors, eigenvalues, canonical};
}

inline Matrix matrix_power(Matrix base, unsigned exponent) {
    if (base.empty() || base.size() != base.front().size()) {
        throw std::runtime_error("matrix power requires square matrix");
    }
    Matrix result = identity_matrix(base.size());
    while (exponent != 0) {
        if ((exponent & 1U) != 0) {
            result = multiply(result, base);
        }
        exponent >>= 1U;
        if (exponent != 0) {
            base = multiply(base, base);
        }
    }
    return result;
}

inline Matrix certified_canonical_power(Eigenbasis const &basis,
                                        unsigned valence,
                                        unsigned exponent) {
    Matrix result = zero_matrix(basis.canonical.size(), basis.canonical.size());
    for (std::size_t index = 0; index < basis.eigenvalues.size(); ++index) {
        result[index][index] = b2interval::integer_power(
            basis.eigenvalues[index], exponent);
    }
    if (valence == 3 && exponent != 0) {
        result[7][8] = b2interval::multiply(
            MpfrInterval(static_cast<long>(exponent)),
            b2interval::integer_power(MpfrInterval::rational(1, 16),
                                      exponent - 1));
    }
    return result;
}

struct Certification {
    unsigned valence;
    std::size_t dimension;
    bool eigen_residual;
    bool krawczyk_inclusion;
    bool inverse_residual;
    bool condition_number;
    bool jordan_power;
    bool spectral_projectors;
    bool deterministic_mgs;
    bool tangent_projector;
};

inline Matrix tangent_projector(unsigned valence) {
    Eigenbasis const seed = analytic_eigenbasis(valence);
    if (seed.eigenvalues.size() < 3 ||
        !certified_same_value(seed.eigenvalues[1],
                              loop_tangent_eigenvalue(valence, 1)) ||
        !certified_same_value(seed.eigenvalues[2],
                              loop_tangent_eigenvalue(valence, 1))) {
        throw std::runtime_error("tangent eigenvalue certification failed");
    }
    return deterministic_projector_block(seed.vectors, {1, 2}).projector;
}

inline Vector extraordinary_vertex_limit_row(unsigned valence) {
    Eigenbasis const basis = analytic_eigenbasis(valence);
    Matrix const inverse = krawczyk_inverse(basis.vectors);
    if (!certified_same_value(basis.eigenvalues.front(), MpfrInterval(1))) {
        throw std::runtime_error("constant eigenvalue certification failed");
    }
    Vector result(basis.vectors.size(), MpfrInterval(0));
    for (std::size_t source = 0; source < result.size(); ++source) {
        result[source] = b2interval::multiply(
            basis.vectors[0][0], inverse[0][source]);
    }
    return result;
}

inline Certification certify_eigenbasis(unsigned valence) {
    Matrix subdivision = stock_subdivision_matrix(valence);
    Eigenbasis seed = analytic_eigenbasis(valence);
    Matrix const certified_inverse = krawczyk_inverse(seed.vectors);
    Eigenbasis basis = deterministic_eigenbasis(valence);
    Matrix eigen_residual = subtract(
        multiply(subdivision, basis.vectors),
        multiply(basis.vectors, basis.canonical));
    bool const eigen_ok =
        residual_contains_zero(eigen_residual, "1e-70") &&
        normalized_eigen_residual(
            subdivision, basis.vectors, basis.canonical,
            eigen_residual, "1e-70");
    Matrix inverse = interval_inverse(basis.vectors);
    Matrix inverse_residual_left = subtract(
        multiply(basis.vectors, inverse), identity_matrix(basis.vectors.size()));
    Matrix inverse_residual_right = subtract(
        multiply(inverse, basis.vectors), identity_matrix(basis.vectors.size()));
    bool const inverse_ok =
        residual_contains_zero(inverse_residual_left, "1e-100") &&
        residual_contains_zero(inverse_residual_right, "1e-100") &&
        residual_contains_zero(subtract(
            multiply(seed.vectors, certified_inverse),
            identity_matrix(seed.vectors.size())), "1e-100") &&
        residual_contains_zero(subtract(
            multiply(certified_inverse, seed.vectors),
            identity_matrix(seed.vectors.size())), "1e-100");
    MpfrInterval condition = b2interval::multiply(
        infinity_norm(basis.vectors), infinity_norm(inverse));
    bool const condition_ok = b2interval::upper_at_most(condition, "1e12");
    bool jordan_ok = true;
    bool projector_ok = false;
    bool krawczyk_ok = true;
    if (valence == 3) {
        for (unsigned exponent = 0; exponent <= 12; ++exponent) {
            Matrix const residual = subtract(
                matrix_power(basis.canonical, exponent),
                certified_canonical_power(basis, valence, exponent));
            jordan_ok = jordan_ok &&
                        residual_contains_zero(residual, "1e-150");
        }
        // The published generalized 1/16 block retains its exact Jordan
        // basis, but all three real invariant spaces are independently
        // enclosed as spectral projectors and subjected to the same
        // source-ID-ordered MGS acceptance protocol.
    }
    std::size_t certified_blocks = 0;
    std::size_t certified_simple_pairs = 0;
    for (std::size_t begin = 0; begin < seed.eigenvalues.size();) {
        std::size_t end = begin + 1;
        while (end < seed.eigenvalues.size() &&
               certified_same_value(seed.eigenvalues[begin],
                                    seed.eigenvalues[end])) ++end;
        for (std::size_t other = 0; other < seed.eigenvalues.size(); ++other) {
            if (other >= begin && other < end) continue;
            MpfrInterval const &left = seed.eigenvalues[begin];
            MpfrInterval const &right = seed.eigenvalues[other];
            if (!mpfr_greater_p(left.lo(), right.hi()) &&
                !mpfr_greater_p(right.lo(), left.hi())) {
                throw std::runtime_error("eigenvalue block separation failed");
            }
        }
        if (end - begin == 1) {
            krawczyk_ok = krawczyk_ok && krawczyk_simple_eigenpair(
                subdivision, seed.eigenvalues[begin],
                matrix_column(seed.vectors, begin));
            ++certified_simple_pairs;
        } else {
            std::vector<std::size_t> columns;
            for (std::size_t column = begin; column < end; ++column)
                columns.push_back(column);
            (void)deterministic_projector_block(seed.vectors, columns);
            ++certified_blocks;
        }
        begin = end;
    }
    bool constant_ok = certified_same_value(
        seed.eigenvalues.front(), MpfrInterval(1));
    for (std::size_t row = 0; row < seed.vectors.size(); ++row) {
        constant_ok = constant_ok &&
            certified_same_value(seed.vectors[row][0], MpfrInterval(1));
    }
    (void)tangent_projector(valence);
    projector_ok = constant_ok && certified_blocks > 0;
    krawczyk_ok = krawczyk_ok && certified_simple_pairs > 0;
    return {valence, basis.vectors.size(), eigen_ok, krawczyk_ok, inverse_ok,
            condition_ok, jordan_ok, projector_ok, projector_ok,
            projector_ok};
}

}  // namespace b2stam
