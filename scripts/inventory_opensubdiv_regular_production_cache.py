#!/usr/bin/env python3
"""Inventory the production regular OpenSubdiv row-cache contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("include/mesh/Regular_limit_surface_row_cache.hpp")
MESH = Path("include/mesh/Mesh.hpp")
EVALUATOR = Path("src/mesh/OpenSubdiv_regular_evaluator.cpp")
AREA = Path("src/mesh/Mesh.cpp")
FORCE = Path("src/energy_force/Compute_energy_and_force_on_mesh.cpp")
SETUP = Path("src/mesh/Mesh_setup_flat.cpp")
TRANSACTION = Path("src/mesh/Loop_topology_transaction.cpp")
TEST = Path("tests/test_surface_geometry_characterization.cpp")
DOC = Path("docs/opensubdiv_regular_production_cache.md")

ANCHORS = {
    "mesh-owned cache": (MESH, "regularLimitSurfaceRowCache_"),
    "backend-neutral table": (CACHE, "RegularLimitSurfaceRowTable"),
    "immutable shared publication": (
        CACHE,
        "std::shared_ptr<const RegularLimitSurfaceRowTable>",
    ),
    "copy starts empty": (CACHE, "A copied mesh starts without backend state."),
    "move transfers state": (CACHE, "transfer_from(other)"),
    "synchronized cache": (CACHE, "mutable std::mutex mutex_"),
    "exact identity snapshot": (CACHE, "std::vector<std::uint8_t> identity_"),
    "schema key": (EVALUATOR, "Cache schema version."),
    "OpenSubdiv version key": (EVALUATOR, "OPENSUBDIV_VERSION_NUMBER"),
    "Loop scheme key": (EVALUATOR, "Sdc::SCHEME_LOOP"),
    "boundary option key": (EVALUATOR, "VTX_BOUNDARY_EDGE_ONLY"),
    "face topology key": (EVALUATOR, "face.adjacentVertices"),
    "source order key": (EVALUATOR, "face.oneRingVertices"),
    "sample coordinate key": (EVALUATOR, "mesh.param.VWU"),
    "quadrature key": (EVALUATOR, "mesh.param.gaussQuadratureCoeff"),
    "reference row key": (EVALUATOR, "mesh.param.shapeFunctions"),
    "runtime bypass": (
        EVALUATOR,
        "if (!opensubdiv_regular_production_routing_requested())",
    ),
    "one publisher lock": (EVALUATOR, "std::lock_guard<std::mutex> lock(cache.mutex_)"),
    "collision-safe identity check": (
        EVALUATOR,
        "cache.identity_ == requestedKey.identity",
    ),
    "area cache lookup": (
        AREA,
        "cached_opensubdiv_regular_shape_functions_by_face(*this)",
    ),
    "force cache lookup": (
        FORCE,
        "cached_opensubdiv_regular_shape_functions_by_face(mesh)",
    ),
    "private topology invalidation seam": (
        MESH,
        "void invalidate_topology_derived_state()",
    ),
    "cache invalidation owned by seam": (
        MESH,
        "regularLimitSurfaceRowCache_.invalidate()",
    ),
    "flat setup invalidation": (SETUP, "invalidate_topology_derived_state()"),
    "import setup invalidation": (AREA, "invalidate_topology_derived_state()"),
    "transaction commit invalidation": (
        TRANSACTION,
        "mesh_.invalidate_topology_derived_state()",
    ),
    "repeated evaluation test": (
        TEST,
        "ReusesOneImmutableTableAcrossAreaForceAndCoordinateUpdates",
    ),
    "non-ghost coordinate source": (TEST, "!mesh.vertices[source].isGhost"),
    "coordinate mutation observable": (
        TEST,
        "directBeforeMutation, directAfterMutation",
    ),
    "coordinate direct parity": (
        TEST,
        "cachedAfterMutation, directAfterMutation",
    ),
    "mutation rebuild test": (
        TEST,
        "FingerprintRebuildsForTopologyAndSamplePlanMutation",
    ),
    "copy move setup test": (
        TEST,
        "SetupInvalidatesWhileCopyStartsEmptyAndMoveTransfers",
    ),
    "concurrent publication test": (
        TEST,
        "ConcurrentReadersPublishOnceAndRuntimeOptOutBypassesCache",
    ),
    "performance evidence": (DOC, "1.95x"),
    "scope boundary": (DOC, "does not add a"),
}

FORBIDDEN_DEFAULT_SURFACES = (
    Path("Makefile"),
    Path(".github"),
    Path("scripts/verify_pr_ready.sh"),
)


def locate(path: Path, needle: str):
    full = ROOT / path
    if not full.is_file():
        return None
    for number, line in enumerate(full.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return {"path": path.as_posix(), "line": number, "source": line.strip()}
    return None


def forbidden_default_dependency_changes():
    leaks = []
    marker = "RegularLimitSurfaceRowCache"
    for relative in FORBIDDEN_DEFAULT_SURFACES:
        full = ROOT / relative
        paths = [full] if full.is_file() else sorted(full.rglob("*")) if full.is_dir() else []
        for path in paths:
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if marker in text:
                leaks.append(path.relative_to(ROOT).as_posix())
    return leaks


def backend_header_leaks():
    leaks = []
    for relative in (CACHE, MESH):
        text = (ROOT / relative).read_text(encoding="utf-8").lower()
        if "#include <opensubdiv/" in text or '#include "opensubdiv/' in text:
            leaks.append(relative.as_posix())
    return leaks


def _cpp_code(text):
    """Mask C++ comments and ordinary/raw literals, preserving positions."""
    text = re.sub(r"\\\r?\n", "", text)
    masked = list(text)
    index = 0
    state = "code"
    raw_start = re.compile(
        r"(?:u8|[uUL])?R\"([^\s()\\]{0,16})\(")
    while index < len(text):
        current = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            raw = raw_start.match(text, index)
            if raw and (index == 0 or not (text[index - 1].isalnum() or
                                           text[index - 1] == "_")):
                closing = ")" + raw.group(1) + '"'
                end = text.find(closing, raw.end())
                end = len(text) if end < 0 else end + len(closing)
                for cursor in range(index, end):
                    if text[cursor] != "\n":
                        masked[cursor] = " "
                index = end
                continue
            if current == "/" and following == "/":
                masked[index] = masked[index + 1] = " "
                index += 2
                state = "line_comment"
                continue
            if current == "/" and following == "*":
                masked[index] = masked[index + 1] = " "
                index += 2
                state = "block_comment"
                continue
            if current in ('"', "'"):
                masked[index] = " "
                state = "string" if current == '"' else "character"
                index += 1
                continue
        elif state == "line_comment":
            if current == "\n":
                state = "code"
            else:
                masked[index] = " "
            index += 1
            continue
        elif state == "block_comment":
            if current == "*" and following == "/":
                masked[index] = masked[index + 1] = " "
                index += 2
                state = "code"
                continue
            if current != "\n":
                masked[index] = " "
            index += 1
            continue
        else:
            if current != "\n":
                masked[index] = " "
            if current == "\\" and following:
                if following != "\n":
                    masked[index + 1] = " "
                index += 2
                continue
            if ((state == "string" and current == '"') or
                    (state == "character" and current == "'")):
                state = "code"
            index += 1
            continue
        index += 1
    return "".join(masked)


_CPP_DIRECTIVE_PREFIX = r"(?:#|%:|\?\?=)"
_INCLUDE_GUARD_NAME = re.compile(r"[A-Z][A-Z0-9_]*_(?:H|HPP)")
_REVIEWED_MESH_HEADER_INCLUDES = (
    "<math.h>", "<cmath>", "<vector>", "<iostream>", "<fstream>",
    "<sstream>", "<string>", "<stdexcept>", "<array>", "<cstdint>",
    "<limits>", "<unordered_map>", "<omp.h>", "<algorithm>",
    '"mesh/Face.hpp"', '"mesh/Vertex.hpp"',
    '"energy_force/Energy.hpp"', '"energy_force/Force.hpp"',
    '"mesh/Gauss_quadrature.hpp"',
    '"mesh/Regular_limit_surface_row_cache.hpp"',
    '"mesh/Loop_topology_transaction.hpp"',
    '"linalg/Linear_algebra.hpp"', '"Parameters.hpp"',
)
_REVIEWED_IMPORT_INCLUDES = (
    '"mesh/Mesh.hpp"', '"mesh/Limit_surface_evaluator.hpp"',
    '"mesh/OpenSubdiv_regular_evaluator.hpp"', "<sstream>", "<stdexcept>",
)
_REVIEWED_FLAT_INCLUDES = ('"mesh/Mesh.hpp"',)
_REVIEWED_TRANSACTION_INCLUDES = (
    '"mesh/Loop_topology_transaction.hpp"', "<algorithm>", "<limits>",
    "<type_traits>", "<utility>", '"mesh/Mesh.hpp"',
)
_REVIEWED_TRANSACTION_COMMIT_SHA256 = (
    "19485b5963d97cd60472e5c66dcf5a275ad6b410fb32270beb7545cd8f4dc748")
_REVIEWED_OTHER_SOURCE_COUNT = 86
_REVIEWED_OTHER_INCLUSION_SHA256 = (
    "8be98f909e50b3e463616d7b050705697a9f2baa730c2973673b166d86482817")


def _source_inclusion_directives(text):
    """Return logical-line include/import directives and their operands."""
    text = re.sub(r"\\\r?\n", "", text)
    code = _cpp_code(text)
    directives = []
    for match in re.finditer(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*"
            r"(include|include_next|import)\b", code, re.MULTILINE):
        line_end = text.find("\n", match.end())
        line_end = len(text) if line_end < 0 else line_end
        directives.append((match.group(1), text[match.end():line_end].strip()))
    return tuple(directives)


def _source_inclusion_surface_sha256(sources):
    surface = [_source_inclusion_directives(source) for source in sources]
    encoded = json.dumps(surface, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _has_unreviewed_macro_directive(code):
    """Reject source macros except conventional empty include guards.

    The protected seam is deliberately checked fail-closed: even a macro whose
    spelling does not mention the protected members can change access labels,
    the overflow guard, or synthesize a member name with token pasting.
    """
    directive = re.compile(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*(define|undef)\b([^\n]*)",
        re.MULTILINE)
    for match in directive.finditer(code):
        if match.group(1) != "define":
            return True
        definition = re.fullmatch(r"\s*([A-Za-z_]\w*)\s*", match.group(2))
        if not definition:
            return True
        name = definition.group(1)
        if not _INCLUDE_GUARD_NAME.fullmatch(name):
            return True
        guard = re.compile(
            rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*ifndef\s+"
            rf"{re.escape(name)}\b", re.MULTILINE)
        if not guard.search(code):
            return True
    return False


def _has_conditional_directive(code):
    """Report conditional preprocessing in a protected implementation file."""
    return bool(re.search(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*"
        r"(?:if|ifdef|ifndef|elif|else|endif)\b",
        code, re.MULTILINE))


def _has_source_inclusion_directive(code):
    """Report source inclusion inside a protected C++ scope."""
    return bool(re.search(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*"
        r"(?:include|include_next|import)\b",
        code, re.MULTILINE))


def _has_preprocessor_directive(code):
    """Report any preprocessing directive inside a protected C++ scope."""
    return bool(re.search(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*[A-Za-z_]\w*\b",
        code, re.MULTILINE))


def _has_nested_source_inclusion(code):
    """Reject fragment expansion inside any scanned brace scope."""
    directive = re.compile(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*"
        r"(?:include|include_next|import)\b", re.MULTILINE)
    return any(code[:match.start()].count("{") !=
               code[:match.start()].count("}")
               for match in directive.finditer(code))


def _mask_cpp_conditionals(code):
    """Exclude every conditional-preprocessor region from positive evidence."""
    masked = []
    depth = 0
    directive = re.compile(
        rf"^\s*{_CPP_DIRECTIVE_PREFIX}\s*([A-Za-z_]\w*)\b")
    for line in code.splitlines(keepends=True):
        match = directive.match(line)
        if match:
            name = match.group(1)
            if name in {"if", "ifdef", "ifndef"}:
                depth += 1
            elif name == "endif":
                depth = max(0, depth - 1)
            masked.append("".join(
                "\n" if character == "\n" else " " for character in line))
        elif depth:
            masked.append("".join(
                "\n" if character == "\n" else " " for character in line))
        else:
            masked.append(line)
    return "".join(masked)


def _direct_access_label(code, position):
    depth = 0
    access = None
    for token in re.finditer(
            r"[{}]|\b(public|protected|private)\s*:", code[:position]):
        if token.group(0) == "{":
            depth += 1
        elif token.group(0) == "}":
            depth = max(0, depth - 1)
        elif depth == 0:
            access = token.group(1)
    return access, depth


def _unique_braced_scope(code, signature_pattern):
    matches = list(re.finditer(signature_pattern, code, re.MULTILINE | re.DOTALL))
    if len(matches) != 1:
        return None
    signature = matches[0]
    opening = code.rfind("{", signature.start(), signature.end())
    if opening < 0:
        return None
    depth = 1
    cursor = opening + 1
    while cursor < len(code) and depth:
        if code[cursor] == "{":
            depth += 1
        elif code[cursor] == "}":
            depth -= 1
        cursor += 1
    if depth:
        return None
    return signature.start(), code[opening + 1:cursor - 1]


def _direct_scope_matches(code, pattern):
    """Return pattern matches that are direct statements in this brace scope."""
    direct = []
    for match in pattern.finditer(code):
        prefix = code[:match.start()]
        if prefix.count("{") == prefix.count("}"):
            direct.append(match)
    return direct


def _scope_begins_with(code, pattern):
    """Require the named direct statement to be the scope's first code."""
    match = pattern.search(code)
    direct_starts = {candidate.start()
                     for candidate in _direct_scope_matches(code, pattern)}
    return bool(match and not code[:match.start()].strip()
                and match.start() in direct_starts)


def _scope_contract_sha256(code):
    """Hash the reviewed lexical scope while ignoring formatting whitespace."""
    normalized = re.sub(r"\s+", " ", code).strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def invalidation_seam_errors_for_sources(
        mesh_header, area, setup, other_mesh_sources=(),
        require_complete_source_surface=False, transaction_source=""):
    lexical_code = [_cpp_code(source) for source in (
        mesh_header, area, setup, transaction_source, *other_mesh_sources)]
    unconditional_code = [_mask_cpp_conditionals(code) for code in lexical_code]
    header_code, area_code, setup_code, transaction_code, *other_code = (
        unconditional_code)
    all_lexical_code = "\n".join(lexical_code)
    all_code = "\n".join(unconditional_code)

    reset_pattern = re.compile(
        r"\bregularLimitSurfaceRowCache_\s*\.\s*invalidate\s*\(\s*\)\s*;")
    seam_call_pattern = re.compile(
        r"\binvalidate_topology_derived_state\s*\(\s*\)\s*;")
    transaction_seam_call_pattern = re.compile(
        r"\bmesh_\s*\.\s*invalidate_topology_derived_state\s*"
        r"\(\s*\)\s*;")
    seam_definition_pattern = re.compile(
        r"\bvoid\s+(?:Mesh::)?invalidate_topology_derived_state\s*"
        r"\(\s*\)\s*\{")
    generation_pattern = re.compile(r"\btopologyGeneration_\b")
    reviewed_seam_body_pattern = re.compile(
        r"\s*if\s*\(\s*topologyGeneration_\s*==\s*"
        r"std::numeric_limits\s*<\s*std::uint64_t\s*>\s*::\s*max\s*"
        r"\(\s*\)\s*\)\s*\{\s*"
        r"throw\s+std::overflow_error\s*\(\s*\)\s*;\s*\}\s*"
        r"regularLimitSurfaceRowCache_\s*\.\s*invalidate\s*"
        r"\(\s*\)\s*;\s*\+\+\s*topologyGeneration_\s*;\s*")
    errors = []

    if require_complete_source_surface and (
            len(other_mesh_sources) != _REVIEWED_OTHER_SOURCE_COUNT or
            _source_inclusion_surface_sha256(other_mesh_sources) !=
            _REVIEWED_OTHER_INCLUSION_SHA256):
        errors.append("all-source include surface has drifted")
    if any(_has_nested_source_inclusion(code) for code in lexical_code[4:]):
        errors.append("source inclusion occurs inside an unreviewed scope")

    reviewed_sources = [
        ("Mesh header", mesh_header, _REVIEWED_MESH_HEADER_INCLUDES),
        ("import setup", area, _REVIEWED_IMPORT_INCLUDES),
        ("flat setup", setup, _REVIEWED_FLAT_INCLUDES),
    ]
    if transaction_source:
        reviewed_sources.append((
            "topology transaction", transaction_source,
            _REVIEWED_TRANSACTION_INCLUDES))
    for name, source, expected in reviewed_sources:
        reviewed = tuple(("include", operand) for operand in expected)
        if _source_inclusion_directives(source) != reviewed:
            errors.append(f"{name} include surface has drifted")

    protected_code = [
        ("Mesh header", lexical_code[0]),
        ("import setup", lexical_code[1]),
        ("flat setup", lexical_code[2]),
    ]
    if transaction_source:
        protected_code.append(("topology transaction", lexical_code[3]))
    for name, code in protected_code:
        if _has_conditional_directive(code):
            errors.append(f"{name} contains conditional preprocessing")

    mesh_class = _unique_braced_scope(
        lexical_code[0], r"\bclass\s+Mesh\b[^;{]*\{")
    if mesh_class is None:
        errors.append("unique Mesh class scope")
    else:
        _, class_body = mesh_class
        if _has_preprocessor_directive(class_body):
            errors.append("Mesh class contains unreviewed preprocessing")
        seam_scope = _unique_braced_scope(
            class_body,
            r"\bvoid\s+invalidate_topology_derived_state\s*\(\s*\)\s*\{")
        if seam_scope is None:
            errors.append("unique topology invalidation seam definition")
        else:
            seam_start, seam_body = seam_scope
            access, seam_depth = _direct_access_label(class_body, seam_start)
            if access != "private" or seam_depth != 0:
                errors.append("topology invalidation seam is not private")
            if len(reset_pattern.findall(seam_body)) != 1:
                errors.append("cache reset is not owned exactly once by seam")
            elif len(_direct_scope_matches(seam_body, reset_pattern)) != 1:
                errors.append("cache reset is not a direct seam statement")
            if not reviewed_seam_body_pattern.fullmatch(seam_body):
                errors.append("topology invalidation seam body has drifted")
        if transaction_source:
            friend_pattern = re.compile(
                r"\bfriend\s+class\s+"
                r"slimed::loop_topology::LoopTopologyTransaction\s*;")
            friend_matches = list(friend_pattern.finditer(class_body))
            if len(friend_matches) != 1:
                errors.append("transaction is not the unique seam friend")
            else:
                access, friend_depth = _direct_access_label(
                    class_body, friend_matches[0].start())
                if access != "private" or friend_depth != 0:
                    errors.append("transaction seam friendship is not private")

    import_scope = _unique_braced_scope(
        lexical_code[1],
        r"\bvoid\s+Mesh::setup_from_vertices_faces\s*\([^)]*\)\s*\{")
    if import_scope is None:
        errors.append("unique import setup scope")
    elif _has_source_inclusion_directive(import_scope[1]):
        errors.append("import setup contains an unreviewed include")
    elif len(seam_call_pattern.findall(import_scope[1])) != 1:
        errors.append("import setup does not call seam exactly once")
    elif not _scope_begins_with(import_scope[1], seam_call_pattern):
        errors.append("import setup does not begin with a direct seam call")

    flat_scope = _unique_braced_scope(
        lexical_code[2], r"\bvoid\s+Mesh::setup_flat\s*\(\s*\)\s*\{")
    if flat_scope is None:
        errors.append("unique flat setup scope")
    elif _has_source_inclusion_directive(flat_scope[1]):
        errors.append("flat setup contains an unreviewed include")
    elif len(seam_call_pattern.findall(flat_scope[1])) != 1:
        errors.append("flat setup does not call seam exactly once")
    elif not _scope_begins_with(flat_scope[1], seam_call_pattern):
        errors.append("flat setup does not begin with a direct seam call")

    if transaction_source:
        transaction_scope = _unique_braced_scope(
            transaction_code,
            r"\bLoopTopologyTransactionResult\s+"
            r"LoopTopologyTransaction::commit\s*\(\s*\)\s*noexcept\s*\{")
        if transaction_scope is None:
            errors.append("unique topology transaction commit scope")
        else:
            _, transaction_body = transaction_scope
            if (_scope_contract_sha256(transaction_body) !=
                    _REVIEWED_TRANSACTION_COMMIT_SHA256):
                errors.append("topology transaction commit body has drifted")
            if _has_source_inclusion_directive(transaction_body):
                errors.append("topology transaction contains an unreviewed include")
            if len(seam_call_pattern.findall(transaction_body)) != 1:
                errors.append("topology transaction does not call seam exactly once")
            transaction_try = _unique_braced_scope(
                transaction_body, r"\btry\s*\{")
            if transaction_try is None:
                errors.append("unique topology transaction invalidation try scope")
            else:
                try_start, try_body = transaction_try
                if (transaction_body[:try_start].count("{") !=
                        transaction_body[:try_start].count("}")):
                    errors.append("topology transaction invalidation is conditional")
                if not transaction_seam_call_pattern.fullmatch(
                        try_body.strip()):
                    errors.append("topology transaction invalidation try body has drifted")

    if len(reset_pattern.findall(all_code)) != 1:
        errors.append("cache reset exists outside the single seam")
    if len(seam_definition_pattern.findall(all_code)) != 1:
        errors.append("topology invalidation seam has unreviewed definitions")
    expected_call_count = 3 if transaction_source else 2
    if len(seam_call_pattern.findall(all_code)) != expected_call_count:
        errors.append("topology invalidation seam has unreviewed callers")
    if (len(generation_pattern.findall(header_code)) != 4 or
            len(generation_pattern.findall(all_code)) != 4):
        errors.append("topology generation has unreviewed references")
    if any(_has_unreviewed_macro_directive(code) for code in lexical_code):
        errors.append("topology invalidation identity is macro-shadowed")
    for name, pattern in (
            ("cache reset", reset_pattern),
            ("topology invalidation seam call", seam_call_pattern),
            ("topology invalidation seam definition", seam_definition_pattern),
            ("topology generation", generation_pattern)):
        if len(pattern.findall(all_lexical_code)) != len(pattern.findall(all_code)):
            errors.append(f"{name} appears in a preprocessor conditional")
    return errors


def _other_cpp_paths():
    excluded = {MESH, AREA, SETUP, TRANSACTION}
    suffixes = {
        ".cpp", ".cc", ".cxx", ".cu", ".mm",
        ".hpp", ".h", ".cuh", ".ipp", ".tpp", ".inl"}
    return [
        path
        for base in (ROOT / "src", ROOT / "include")
        for path in sorted(base.rglob("*"))
        if path.is_file() and path.suffix in suffixes
        and path.relative_to(ROOT) not in excluded
    ]


def invalidation_seam_errors():
    other_sources = [path.read_text(encoding="utf-8")
                     for path in _other_cpp_paths()]
    return invalidation_seam_errors_for_sources(
        (ROOT / MESH).read_text(encoding="utf-8"),
        (ROOT / AREA).read_text(encoding="utf-8"),
        (ROOT / SETUP).read_text(encoding="utf-8"),
        other_sources,
        require_complete_source_surface=True,
        transaction_source=(ROOT / TRANSACTION).read_text(encoding="utf-8"),
    )


def payload():
    located = {}
    missing = []
    for name, (path, needle) in ANCHORS.items():
        match = locate(path, needle)
        if match is None:
            missing.append({"name": name, "path": path.as_posix(), "needle": needle})
        else:
            located[name] = match
    default_leaks = forbidden_default_dependency_changes()
    header_leaks = backend_header_leaks()
    seam_errors = invalidation_seam_errors()
    return {
        "status": "passed" if not missing and not default_leaks and not header_leaks
        and not seam_errors else "failed",
        "kind": "production_regular_opensubdiv_row_cache_inventory",
        "production_cache_implemented": True,
        "default_opensubdiv_dependency": False,
        "broader_valence_in_scope": False,
        "formula_or_scatter_change": False,
        "openmp_reduction_change": False,
        "located": located,
        "missing": missing,
        "default_surface_leaks": default_leaks,
        "backend_header_leaks": header_leaks,
        "invalidation_seam_errors": seam_errors,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = payload()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("# Production Regular OpenSubdiv Row Cache Inventory")
        print(f"status: {result['status']}")
        print(f"anchors: {len(result['located'])}/{len(ANCHORS)}")
        print(f"default surface leaks: {len(result['default_surface_leaks'])}")
        print(f"backend header leaks: {len(result['backend_header_leaks'])}")
        print(f"invalidation seam errors: {len(result['invalidation_seam_errors'])}")
    return 1 if args.check and result["status"] != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
