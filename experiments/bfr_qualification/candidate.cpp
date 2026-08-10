// B2 proof-only Bfr target and Far regression-comparator harness.
// This translation unit has no production caller and changes no route.

#include <opensubdiv/bfr/refinerSurfaceFactory.h>
#include <opensubdiv/bfr/surface.h>
#include <opensubdiv/far/patchTableFactory.h>
#include <opensubdiv/far/stencilTable.h>
#include <opensubdiv/far/stencilTableFactory.h>
#include <opensubdiv/far/topologyDescriptor.h>
#include <opensubdiv/far/topologyRefinerFactory.h>
#include <opensubdiv/version.h>

#include "fixture_mesh.hpp"

#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/ps/IOPowerSources.h>
#include <IOKit/ps/IOPSKeys.h>
#include <objc/message.h>
#include <objc/runtime.h>

#if OPENSUBDIV_VERSION_NUMBER != 30700
#error "B2 is qualified only for OpenSubdiv 3.7.0"
#endif

#include <algorithm>
#include <array>
#include <cstdint>
#include <cmath>
#include <condition_variable>
#include <cstdlib>
#include <exception>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <mutex>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include <mach/mach.h>
#include <mach/mach_time.h>
#include <sys/sysctl.h>
#include <sys/utsname.h>

namespace {

using namespace OpenSubdiv;

constexpr int kRowCount = 6;
constexpr double kInvariantTolerance = 1.0e-12;
// Exact +1 sample weight is a validation-only sentinel.  It is intentionally
// absent from every row, integrand, quadrature, and arithmetic expression.
constexpr double kValidationOnlySentinel = 1.0;

struct RefinerDeleter {
    void operator()(Far::TopologyRefiner *value) const { delete value; }
};

template <class Value>
struct ConstDeleter {
    void operator()(Value const *value) const { delete value; }
};

using RefinerPtr = std::unique_ptr<Far::TopologyRefiner, RefinerDeleter>;

struct Rows {
    std::array<std::vector<int>, kRowCount> ids;
    std::array<std::vector<double>, kRowCount> coefficients;
};

struct Sample {
    std::string id;
    int localCorner;
    double u;
    double v;
};

struct RowGroup {
    int face;
    Sample sample;
    Rows rows;
};

struct RowPackage {
    std::vector<RowGroup> groups;
    double maxRowSumError = 0.0;
    std::uint64_t maxRetainedPayloadPerFace = 0;
};

struct Preparation {
    RefinerPtr refiner;
    std::unique_ptr<Bfr::RefinerSurfaceFactoryBase> bfrFactory;
    std::unique_ptr<Far::LimitStencilTableReal<double> const,
                    ConstDeleter<Far::LimitStencilTableReal<double> > > farTable;
    std::unique_ptr<RowPackage> package;
    std::uint64_t elapsedNanoseconds = 0;
};

struct RssLedger {
    std::uint64_t baseline = 0;
    std::uint64_t peakDeltaBytes = 0;
    std::uint64_t afterRefinerConstruction = 0;
    std::uint64_t afterFactoryOrCacheConstruction = 0;
    std::uint64_t afterEachCompletedFaceRowInsertion = 0;
    std::uint64_t afterImmutablePackagePublication = 0;
    std::uint64_t afterRowPackageDestruction = 0;
    std::uint64_t afterFactoryOrCacheDestruction = 0;
    std::uint64_t afterRefinerDestruction = 0;
};

struct PlatformProbe {
    bool fingerprintQueriesOk = true;
    std::string architecture;
    std::string macosVersion;
    std::string macosBuild;
    std::string hwModel;
    std::string chip;
    std::uint64_t hwMemsizeBytes = 0;
    int hwNcpu = 0;
    int hwPhysicalcpu = 0;
    int hwLogicalcpu = 0;
    int hwPerflevel0Physicalcpu = 0;
    int hwPerflevel0Logicalcpu = 0;
    int hwPerflevel1Physicalcpu = 0;
    int hwPerflevel1Logicalcpu = 0;
    int kernHvVmmPresent = -1;
    bool powerQueryOk = false;
    std::string powerRaw;
    std::string powerValue;
    bool thermalQueryOk = false;
    long thermalRaw = -1;
    std::string thermalValue;
};

bool sysctl_string(char const *name, std::string &value) {
    std::size_t size = 0;
    if (sysctlbyname(name, nullptr, &size, nullptr, 0) != 0 || size == 0) return false;
    std::vector<char> buffer(size, '\0');
    if (sysctlbyname(name, &buffer[0], &size, nullptr, 0) != 0 || size == 0) return false;
    if (buffer[size - 1] == '\0') --size;
    value.assign(&buffer[0], size);
    return true;
}

template <class Value>
bool sysctl_scalar(char const *name, Value &value) {
    std::size_t size = sizeof(value);
    Value observed = Value();
    if (sysctlbyname(name, &observed, &size, nullptr, 0) != 0 || size != sizeof(Value)) {
        return false;
    }
    value = observed;
    return true;
}

std::string cf_string(CFStringRef value) {
    if (!value) return std::string();
    CFIndex const length = CFStringGetLength(value);
    CFIndex const capacity = CFStringGetMaximumSizeForEncoding(
        length, kCFStringEncodingUTF8) + 1;
    if (capacity <= 0) return std::string();
    std::vector<char> buffer(static_cast<std::size_t>(capacity), '\0');
    if (!CFStringGetCString(value, &buffer[0], capacity, kCFStringEncodingUTF8)) {
        return std::string();
    }
    return std::string(&buffer[0]);
}

PlatformProbe capture_platform_probe() {
    PlatformProbe probe;
    struct utsname names;
    if (uname(&names) != 0) {
        probe.fingerprintQueriesOk = false;
    } else {
        probe.architecture = names.machine;
    }
    probe.fingerprintQueriesOk =
        sysctl_string("kern.osproductversion", probe.macosVersion) &&
        probe.fingerprintQueriesOk;
    probe.fingerprintQueriesOk =
        sysctl_string("kern.osversion", probe.macosBuild) &&
        probe.fingerprintQueriesOk;
    probe.fingerprintQueriesOk =
        sysctl_string("hw.model", probe.hwModel) && probe.fingerprintQueriesOk;
    probe.fingerprintQueriesOk =
        sysctl_string("machdep.cpu.brand_string", probe.chip) &&
        probe.fingerprintQueriesOk;
    probe.fingerprintQueriesOk =
        sysctl_scalar("hw.memsize", probe.hwMemsizeBytes) &&
        probe.fingerprintQueriesOk;
    probe.fingerprintQueriesOk =
        sysctl_scalar("hw.ncpu", probe.hwNcpu) && probe.fingerprintQueriesOk;
    probe.fingerprintQueriesOk =
        sysctl_scalar("hw.physicalcpu", probe.hwPhysicalcpu) &&
        probe.fingerprintQueriesOk;
    probe.fingerprintQueriesOk =
        sysctl_scalar("hw.logicalcpu", probe.hwLogicalcpu) &&
        probe.fingerprintQueriesOk;
    probe.fingerprintQueriesOk =
        sysctl_scalar("hw.perflevel0.physicalcpu", probe.hwPerflevel0Physicalcpu) &&
        probe.fingerprintQueriesOk;
    probe.fingerprintQueriesOk =
        sysctl_scalar("hw.perflevel0.logicalcpu", probe.hwPerflevel0Logicalcpu) &&
        probe.fingerprintQueriesOk;
    probe.fingerprintQueriesOk =
        sysctl_scalar("hw.perflevel1.physicalcpu", probe.hwPerflevel1Physicalcpu) &&
        probe.fingerprintQueriesOk;
    probe.fingerprintQueriesOk =
        sysctl_scalar("hw.perflevel1.logicalcpu", probe.hwPerflevel1Logicalcpu) &&
        probe.fingerprintQueriesOk;
    probe.fingerprintQueriesOk =
        sysctl_scalar("kern.hv_vmm_present", probe.kernHvVmmPresent) &&
        probe.fingerprintQueriesOk;

    CFTypeRef const snapshot = IOPSCopyPowerSourcesInfo();
    if (snapshot) {
        probe.powerRaw = cf_string(IOPSGetProvidingPowerSourceType(snapshot));
        probe.powerQueryOk = !probe.powerRaw.empty();
        if (probe.powerRaw == kIOPSACPowerValue) {
            probe.powerValue = "kIOPSACPowerValue";
        } else if (probe.powerRaw == kIOPSBatteryPowerValue) {
            probe.powerValue = "kIOPSBatteryPowerValue";
        } else if (probe.powerRaw == kIOPSOffLineValue) {
            probe.powerValue = "kIOPSOffLineValue";
        } else {
            probe.powerValue = "UNKNOWN_POWER_VALUE";
        }
        CFRelease(snapshot);
    }

    Class const processInfoClass = objc_getClass("NSProcessInfo");
    SEL const processInfoSelector = sel_registerName("processInfo");
    SEL const thermalSelector = sel_registerName("thermalState");
    if (processInfoClass && processInfoSelector && thermalSelector) {
        typedef id (*ObjectMessage)(id, SEL);
        typedef long (*LongMessage)(id, SEL);
        ObjectMessage const sendObject = reinterpret_cast<ObjectMessage>(objc_msgSend);
        LongMessage const sendLong = reinterpret_cast<LongMessage>(objc_msgSend);
        id const processInfo = sendObject(reinterpret_cast<id>(processInfoClass),
                                          processInfoSelector);
        if (processInfo) {
            probe.thermalRaw = sendLong(processInfo, thermalSelector);
            probe.thermalQueryOk = probe.thermalRaw >= 0 && probe.thermalRaw <= 3;
            static char const *const states[] = {
                "NSProcessInfoThermalStateNominal", "NSProcessInfoThermalStateFair",
                "NSProcessInfoThermalStateSerious", "NSProcessInfoThermalStateCritical"};
            probe.thermalValue = probe.thermalQueryOk
                ? states[probe.thermalRaw] : "UNKNOWN_THERMAL_STATE";
        }
    }
    return probe;
}

void emit_json_string(std::ostream &output, std::string const &value) {
    output << '"';
    for (std::string::const_iterator character = value.begin();
         character != value.end(); ++character) {
        unsigned char const byte = static_cast<unsigned char>(*character);
        if (byte == '"' || byte == '\\') output << '\\' << *character;
        else if (byte == '\n') output << "\\n";
        else if (byte == '\r') output << "\\r";
        else if (byte == '\t') output << "\\t";
        else if (byte < 0x20U) output << "?";
        else output << *character;
    }
    output << '"';
}

int platform_probe() {
    PlatformProbe const probe = capture_platform_probe();
    std::cout << "{\"schema_version\":1,\"kind\":\"bfr_platform_probe\","
              << "\"status\":\"ok\",\"finite\":true,\"fingerprint_queries_ok\":"
              << (probe.fingerprintQueriesOk ? "true" : "false")
              << ",\"fingerprint\":{";
    std::cout << "\"architecture\":"; emit_json_string(std::cout, probe.architecture);
    std::cout << ",\"chip\":"; emit_json_string(std::cout, probe.chip);
    std::cout << ",\"hw_logicalcpu\":" << probe.hwLogicalcpu
              << ",\"hw_memsize_bytes\":" << probe.hwMemsizeBytes
              << ",\"hw_model\":"; emit_json_string(std::cout, probe.hwModel);
    std::cout << ",\"hw_ncpu\":" << probe.hwNcpu
              << ",\"hw_perflevel0_logicalcpu\":" << probe.hwPerflevel0Logicalcpu
              << ",\"hw_perflevel0_physicalcpu\":" << probe.hwPerflevel0Physicalcpu
              << ",\"hw_perflevel1_logicalcpu\":" << probe.hwPerflevel1Logicalcpu
              << ",\"hw_perflevel1_physicalcpu\":" << probe.hwPerflevel1Physicalcpu
              << ",\"hw_physicalcpu\":" << probe.hwPhysicalcpu
              << ",\"kern_hv_vmm_present\":" << probe.kernHvVmmPresent
              << ",\"macos_build\":"; emit_json_string(std::cout, probe.macosBuild);
    std::cout << ",\"macos_version\":"; emit_json_string(std::cout, probe.macosVersion);
    std::cout << "},\"power\":{\"api\":\"IOPSCopyPowerSourcesInfo plus IOPSGetProvidingPowerSourceType\","
              << "\"query_ok\":" << (probe.powerQueryOk ? "true" : "false")
              << ",\"raw\":"; emit_json_string(std::cout, probe.powerRaw);
    std::cout << ",\"value\":"; emit_json_string(std::cout, probe.powerValue);
    std::cout << "},\"thermal\":{\"api\":\"NSProcessInfo.thermalState\","
              << "\"query_ok\":" << (probe.thermalQueryOk ? "true" : "false")
              << ",\"raw\":" << probe.thermalRaw << ",\"value\":";
    emit_json_string(std::cout, probe.thermalValue);
    std::cout << "}}\n";
    return 0;
}

std::uint64_t continuous_nanoseconds() {
    mach_timebase_info_data_t timebase;
    if (mach_timebase_info(&timebase) != KERN_SUCCESS || timebase.denom == 0) {
        throw std::runtime_error("MEASUREMENT_PROTOCOL_FAILURE_TIMEBASE");
    }
    std::uint64_t const ticks = mach_continuous_time();
    if (ticks > std::numeric_limits<std::uint64_t>::max() / timebase.numer) {
        throw std::runtime_error("MEASUREMENT_PROTOCOL_FAILURE_CLOCK_OVERFLOW");
    }
    return ticks * timebase.numer / timebase.denom;
}

std::uint64_t resident_bytes() {
    mach_task_basic_info_data_t info;
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    if (task_info(mach_task_self(), MACH_TASK_BASIC_INFO,
                  reinterpret_cast<task_info_t>(&info), &count) != KERN_SUCCESS ||
        count != MACH_TASK_BASIC_INFO_COUNT) {
        throw std::runtime_error("MEASUREMENT_PROTOCOL_FAILURE_RSS");
    }
    return static_cast<std::uint64_t>(info.resident_size);
}

void observe_rss(std::uint64_t baseline, std::uint64_t &peak) {
    std::uint64_t const current = resident_bytes();
    std::uint64_t const delta = current > baseline ? current - baseline : 0;
    peak = std::max(peak, delta);
}

void observe_named_rss(RssLedger *ledger, std::uint64_t RssLedger::*counter) {
    if (!ledger) return;
    observe_rss(ledger->baseline, ledger->peakDeltaBytes);
    ++(ledger->*counter);
}

std::vector<Sample> face_samples(b2fixture::Mesh const &mesh, int face) {
    static const int regular[][2] = {
        {1, 1}, {1, 2}, {2, 1}, {1, 3}, {2, 2},
        {3, 1}, {1, 4}, {2, 3}, {3, 2}, {4, 1},
    };
    std::vector<Sample> samples;
    samples.reserve(82);
    for (int index = 0; index < 10; ++index) {
        std::ostringstream id;
        int const sum = regular[index][0] + regular[index][1];
        id << "tri-l6-s0" << sum << "-u0" << regular[index][0]
           << "-v0" << regular[index][1];
        samples.push_back(Sample{id.str(), -1, regular[index][0] / 6.0,
                                 regular[index][1] / 6.0});
    }
    static const int rays[][2] = {{1, 3}, {2, 2}, {3, 1}};
    for (int corner = 0; corner < 3; ++corner) {
        int const vertex = mesh.faces.at(static_cast<std::size_t>(face))[corner];
        if (mesh.valences.at(static_cast<std::size_t>(vertex)) == 6) {
            continue;
        }
        for (int exponent = 1; exponent <= 8; ++exponent) {
            double const radius = std::ldexp(1.0, -exponent);
            for (int ray = 0; ray < 3; ++ray) {
                double const xi = radius * rays[ray][0] / 4.0;
                double const eta = radius * rays[ray][1] / 4.0;
                double u = 0.0;
                double v = 0.0;
                if (corner == 0) {
                    u = xi; v = eta;
                } else if (corner == 1) {
                    u = 1.0 - xi - eta; v = xi;
                } else {
                    u = eta; v = 1.0 - xi - eta;
                }
                std::ostringstream id;
                id << "trend-r0" << exponent << "-ray0" << ray;
                samples.push_back(Sample{id.str(), corner, u, v});
            }
        }
    }
    return samples;
}

RefinerPtr make_tetrahedron_refiner() {
    static const int vertsPerFace[] = {3, 3, 3, 3};
    static const int vertexIndices[] = {
        0, 2, 1,
        0, 1, 3,
        0, 3, 2,
        1, 2, 3,
    };
    Far::TopologyDescriptor descriptor;
    descriptor.numVertices = 4;
    descriptor.numFaces = 4;
    descriptor.numVertsPerFace = vertsPerFace;
    descriptor.vertIndicesPerFace = vertexIndices;
    Sdc::Options schemeOptions;
    schemeOptions.SetVtxBoundaryInterpolation(Sdc::Options::VTX_BOUNDARY_EDGE_ONLY);
    return RefinerPtr(Far::TopologyRefinerFactory<Far::TopologyDescriptor>::Create(
        descriptor,
        Far::TopologyRefinerFactory<Far::TopologyDescriptor>::Options(
            Sdc::SCHEME_LOOP, schemeOptions)));
}

RefinerPtr make_mesh_refiner(b2fixture::Mesh const &mesh) {
    std::vector<int> vertsPerFace(mesh.faces.size(), 3);
    std::vector<int> vertexIndices;
    vertexIndices.reserve(mesh.faces.size() * 3);
    for (std::size_t face = 0; face < mesh.faces.size(); ++face) {
        vertexIndices.push_back(mesh.faces[face][0]);
        vertexIndices.push_back(mesh.faces[face][1]);
        vertexIndices.push_back(mesh.faces[face][2]);
    }
    Far::TopologyDescriptor descriptor;
    descriptor.numVertices = static_cast<int>(mesh.vertices.size());
    descriptor.numFaces = static_cast<int>(mesh.faces.size());
    descriptor.numVertsPerFace = vertsPerFace.data();
    descriptor.vertIndicesPerFace = vertexIndices.data();
    Sdc::Options schemeOptions;
    schemeOptions.SetVtxBoundaryInterpolation(Sdc::Options::VTX_BOUNDARY_EDGE_ONLY);
    RefinerPtr result(Far::TopologyRefinerFactory<Far::TopologyDescriptor>::Create(
        descriptor,
        Far::TopologyRefinerFactory<Far::TopologyDescriptor>::Options(
            Sdc::SCHEME_LOOP, schemeOptions)));
    if (!result) {
        throw std::runtime_error("full-mesh TopologyRefiner construction failed");
    }
    return result;
}

void canonicalize_row(std::vector<int> const &inputIds,
                      std::vector<double> const &inputCoefficients,
                      std::vector<int> &ids,
                      std::vector<double> &coefficients) {
    if (inputIds.size() != inputCoefficients.size()) {
        throw std::runtime_error("row cardinality mismatch");
    }
    std::vector<std::pair<int, double> > entries;
    for (std::size_t index = 0; index < inputIds.size(); ++index) {
        if (inputIds[index] < 0 || !std::isfinite(inputCoefficients[index])) {
            throw std::runtime_error("invalid source-keyed coefficient");
        }
        entries.push_back(std::make_pair(inputIds[index], inputCoefficients[index]));
    }
    std::sort(entries.begin(), entries.end());
    for (std::size_t index = 0; index < entries.size(); ++index) {
        if (!ids.empty() && ids.back() == entries[index].first) {
            coefficients.back() += entries[index].second;
        } else {
            ids.push_back(entries[index].first);
            coefficients.push_back(entries[index].second);
        }
    }
}

template <class Factory>
Rows evaluate_bfr_surface(Factory const &factory, int face, double u, double v) {
    if (!factory.FaceHasLimitSurface(face)) {
        throw std::runtime_error("Bfr reports no limit surface");
    }
    Bfr::Surface<double> surface;
    if (!factory.InitVertexSurface(face, &surface) || !surface.IsValid()) {
        throw std::runtime_error("Bfr surface initialization failed");
    }
    int const count = surface.GetNumControlPoints();
    if (count <= 0) {
        throw std::runtime_error("Bfr returned no original controls");
    }
    std::vector<int> sourceIds(static_cast<std::size_t>(count));
    if (surface.GetControlPointIndices(sourceIds.data()) != count) {
        throw std::runtime_error("Bfr source reconstruction was incomplete");
    }
    std::array<std::vector<double>, kRowCount> raw;
    for (int row = 0; row < kRowCount; ++row) {
        raw[row].resize(static_cast<std::size_t>(count));
    }
    double uv[2] = {u, v};
    surface.EvaluateStencil(uv, raw[0].data(), raw[1].data(), raw[2].data(),
                            raw[3].data(), raw[4].data(), raw[5].data());
    Rows rows;
    for (int row = 0; row < kRowCount; ++row) {
        canonicalize_row(sourceIds, raw[row], rows.ids[row], rows.coefficients[row]);
    }
    return rows;
}

Rows evaluate_bfr(Far::TopologyRefiner const &refiner, double u, double v) {
    Bfr::SurfaceFactory::Options options;
    options.EnableCaching(false);
    options.SetApproxLevelSmooth(8);
    options.SetApproxLevelSharp(6);
    Bfr::RefinerSurfaceFactory<> factory(refiner, options);
    return evaluate_bfr_surface(factory, 0, u, v);
}

Rows evaluate_far(Far::TopologyRefiner &refiner, int face, int isolationLevel,
                  double u, double v, bool refine) {
    Far::PatchTableFactory::Options patchOptions(isolationLevel);
    patchOptions.endCapType = Far::PatchTableFactory::Options::ENDCAP_GREGORY_BASIS;
    Far::TopologyRefiner::AdaptiveOptions adaptive = patchOptions.GetRefineAdaptiveOptions();
    adaptive.SetIsolationLevel(8);
    if (refine) {
        refiner.RefineAdaptive(adaptive);
    }

    using Factory = Far::LimitStencilTableFactoryReal<double>;
    Factory::LocationArray location;
    location.ptexIdx = face;
    location.numLocations = 1;
    location.s = &u;
    location.t = &v;
    Factory::LocationArrayVec locations;
    locations.push_back(location);
    Factory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;
    std::unique_ptr<Far::LimitStencilTableReal<double> const,
                    ConstDeleter<Far::LimitStencilTableReal<double> > > table(
        Factory::Create(refiner, locations, nullptr, nullptr, stencilOptions));
    if (!table || table->GetNumStencils() != 1) {
        throw std::runtime_error("Far limit-stencil construction failed");
    }
    Far::LimitStencilReal<double> stencil = table->GetLimitStencil(0);
    std::array<double const *, kRowCount> raw = {{
        stencil.GetWeights(), stencil.GetDuWeights(), stencil.GetDvWeights(),
        stencil.GetDuuWeights(), stencil.GetDuvWeights(), stencil.GetDvvWeights(),
    }};
    for (int row = 0; row < kRowCount; ++row) {
        if (!raw[row]) {
            throw std::runtime_error("Far omitted a derivative order");
        }
    }
    std::vector<int> ids(stencil.GetVertexIndices(),
                         stencil.GetVertexIndices() + stencil.GetSize());
    Rows rows;
    for (int row = 0; row < kRowCount; ++row) {
        std::vector<double> coefficients(raw[row], raw[row] + stencil.GetSize());
        canonicalize_row(ids, coefficients, rows.ids[row], rows.coefficients[row]);
    }
    return rows;
}


Rows evaluate_far(Far::TopologyRefiner &refiner, double u, double v) {
    return evaluate_far(refiner, 0, 8, u, v, true);
}

double sum(std::vector<double> const &values) {
    return std::accumulate(values.begin(), values.end(), 0.0);
}

void validate_rows(Rows const &rows, char const *candidate, bool enforceInvariant = true) {
    for (int row = 0; row < kRowCount; ++row) {
        if (rows.ids[row].empty() || rows.ids[row].size() != rows.coefficients[row].size() ||
            !std::is_sorted(rows.ids[row].begin(), rows.ids[row].end())) {
            throw std::runtime_error(std::string(candidate) + " malformed source row");
        }
        double const expected = row == 0 ? 1.0 : 0.0;
        if (enforceInvariant &&
            std::abs(sum(rows.coefficients[row]) - expected) > kInvariantTolerance) {
            throw std::runtime_error(std::string(candidate) + " row invariant failed");
        }
    }
}

void append_group(RowPackage &package, int face, Sample const &sample,
                  Rows rows, char const *candidate) {
    validate_rows(rows, candidate, false);
    for (int row = 0; row < kRowCount; ++row) {
        double const expected = row == 0 ? 1.0 : 0.0;
        package.maxRowSumError = std::max(
            package.maxRowSumError, std::abs(sum(rows.coefficients[row]) - expected));
    }
    package.groups.push_back(RowGroup{face, sample, std::move(rows)});
}

void finalize_payload(RowPackage &package, int faceCount) {
    for (int face = 0; face < faceCount; ++face) {
        std::set<int> sourceUnion;
        std::uint64_t sampleCount = 0;
        std::uint64_t coefficientCount = 0;
        for (std::size_t groupIndex = 0; groupIndex < package.groups.size(); ++groupIndex) {
            RowGroup const &group = package.groups[groupIndex];
            if (group.face != face) continue;
            ++sampleCount;
            for (int row = 0; row < kRowCount; ++row) {
                coefficientCount += group.rows.coefficients[row].size();
                sourceUnion.insert(group.rows.ids[row].begin(), group.rows.ids[row].end());
            }
        }
        std::uint64_t const payload = UINT64_C(12) + UINT64_C(4) * sourceUnion.size() +
            UINT64_C(72) * sampleCount + UINT64_C(12) * coefficientCount;
        package.maxRetainedPayloadPerFace =
            std::max(package.maxRetainedPayloadPerFace, payload);
    }
}

template <class Factory>
std::unique_ptr<RowPackage> build_bfr_workload(b2fixture::Mesh const &mesh,
                                               Factory const &factory,
                                               RssLedger *rss) {
    std::unique_ptr<RowPackage> package(new RowPackage());
    for (int face = 0; face < static_cast<int>(mesh.faces.size()); ++face) {
        std::vector<Sample> const samples = face_samples(mesh, face);
        for (std::size_t sample = 0; sample < samples.size(); ++sample) {
            append_group(*package, face, samples[sample],
                         evaluate_bfr_surface(factory, face,
                                              samples[sample].u, samples[sample].v),
                         "Bfr");
            observe_named_rss(rss, &RssLedger::afterEachCompletedFaceRowInsertion);
        }
    }
    finalize_payload(*package, static_cast<int>(mesh.faces.size()));
    observe_named_rss(rss, &RssLedger::afterImmutablePackagePublication);
    return package;
}

Preparation prepare_bfr_case(b2fixture::Mesh const &mesh, int level,
                             std::string const &mode, RssLedger *rss) {
    Preparation result;
    std::uint64_t const begin = continuous_nanoseconds();
    result.refiner = make_mesh_refiner(mesh);
    observe_named_rss(rss, &RssLedger::afterRefinerConstruction);
    Bfr::SurfaceFactory::Options options;
    options.EnableCaching(mode != "cache_disabled");
    options.SetApproxLevelSmooth(level);
    options.SetApproxLevelSharp(6);
    if (mode != "cache_disabled" && mode != "SurfaceFactoryCache_serial") {
        throw std::runtime_error("invalid Bfr numeric cache mode");
    }
    result.bfrFactory.reset(new Bfr::RefinerSurfaceFactory<>(*result.refiner, options));
    observe_named_rss(rss, &RssLedger::afterFactoryOrCacheConstruction);
    result.package = build_bfr_workload(mesh, *result.bfrFactory, rss);
    result.elapsedNanoseconds = continuous_nanoseconds() - begin;
    return result;
}

Rows rows_from_far_stencil(Far::LimitStencilReal<double> const &stencil) {
    std::array<double const *, kRowCount> raw = {{
        stencil.GetWeights(), stencil.GetDuWeights(), stencil.GetDvWeights(),
        stencil.GetDuuWeights(), stencil.GetDuvWeights(), stencil.GetDvvWeights(),
    }};
    for (int row = 0; row < kRowCount; ++row) {
        if (!raw[row]) throw std::runtime_error("Far omitted a derivative order");
    }
    std::vector<int> ids(stencil.GetVertexIndices(),
                         stencil.GetVertexIndices() + stencil.GetSize());
    Rows rows;
    for (int row = 0; row < kRowCount; ++row) {
        std::vector<double> coefficients(raw[row], raw[row] + stencil.GetSize());
        canonicalize_row(ids, coefficients, rows.ids[row], rows.coefficients[row]);
    }
    return rows;
}

Preparation prepare_far_case(b2fixture::Mesh const &mesh, int level,
                             RssLedger *rss) {
    Preparation result;
    std::uint64_t const begin = continuous_nanoseconds();
    result.refiner = make_mesh_refiner(mesh);
    observe_named_rss(rss, &RssLedger::afterRefinerConstruction);
    Far::PatchTableFactory::Options patchOptions(level);
    patchOptions.endCapType = Far::PatchTableFactory::Options::ENDCAP_GREGORY_BASIS;
    Far::TopologyRefiner::AdaptiveOptions adaptive = patchOptions.GetRefineAdaptiveOptions();
    adaptive.SetIsolationLevel(level);
    result.refiner->RefineAdaptive(adaptive);

    using Factory = Far::LimitStencilTableFactoryReal<double>;
    std::vector<std::vector<Sample> > samplesByFace(mesh.faces.size());
    std::vector<std::vector<double> > uByFace(mesh.faces.size());
    std::vector<std::vector<double> > vByFace(mesh.faces.size());
    for (std::size_t face = 0; face < mesh.faces.size(); ++face) {
        samplesByFace[face] = face_samples(mesh, static_cast<int>(face));
        for (std::size_t sample = 0; sample < samplesByFace[face].size(); ++sample) {
            uByFace[face].push_back(samplesByFace[face][sample].u);
            vByFace[face].push_back(samplesByFace[face][sample].v);
        }
    }
    Factory::LocationArrayVec locations;
    locations.reserve(mesh.faces.size());
    for (std::size_t face = 0; face < mesh.faces.size(); ++face) {
        Factory::LocationArray location;
        location.ptexIdx = static_cast<int>(face);
        location.numLocations = static_cast<int>(samplesByFace[face].size());
        location.s = uByFace[face].data();
        location.t = vByFace[face].data();
        locations.push_back(location);
    }
    Factory::Options stencilOptions;
    stencilOptions.generate1stDerivatives = true;
    stencilOptions.generate2ndDerivatives = true;
    result.farTable.reset(
        Factory::Create(*result.refiner, locations, nullptr, nullptr, stencilOptions));
    observe_named_rss(rss, &RssLedger::afterFactoryOrCacheConstruction);
    std::size_t expectedCount = 0;
    for (std::size_t face = 0; face < samplesByFace.size(); ++face) {
        expectedCount += samplesByFace[face].size();
    }
    if (!result.farTable ||
        result.farTable->GetNumStencils() != static_cast<int>(expectedCount)) {
        throw std::runtime_error("Far full-workload limit-stencil construction failed");
    }
    result.package.reset(new RowPackage());
    int stencilIndex = 0;
    for (int face = 0; face < static_cast<int>(mesh.faces.size()); ++face) {
        for (std::size_t sample = 0; sample < samplesByFace[static_cast<std::size_t>(face)].size(); ++sample) {
            append_group(*result.package, face,
                         samplesByFace[static_cast<std::size_t>(face)][sample],
                         rows_from_far_stencil(
                             result.farTable->GetLimitStencil(stencilIndex++)), "Far");
            observe_named_rss(rss, &RssLedger::afterEachCompletedFaceRowInsertion);
        }
    }
    finalize_payload(*result.package, static_cast<int>(mesh.faces.size()));
    observe_named_rss(rss, &RssLedger::afterImmutablePackagePublication);
    result.elapsedNanoseconds = continuous_nanoseconds() - begin;
    return result;
}

double maximum_geometry_spread(Rows const &left, Rows const &right) {
    static const std::array<std::array<double, 3>, 4> coordinates = {{
        {{-0.57735026918962584, -0.57735026918962584, -0.57735026918962584}},
        {{-0.57735026918962584, 0.57735026918962584, 0.57735026918962584}},
        {{0.57735026918962584, -0.57735026918962584, 0.57735026918962584}},
        {{0.57735026918962584, 0.57735026918962584, -0.57735026918962584}},
    }};
    double maximum = 0.0;
    for (int row = 0; row < kRowCount; ++row) {
        for (int axis = 0; axis < 3; ++axis) {
            double a = 0.0;
            double b = 0.0;
            for (std::size_t index = 0; index < left.ids[row].size(); ++index) {
                a += left.coefficients[row][index] * coordinates.at(static_cast<std::size_t>(left.ids[row][index]))[axis];
            }
            for (std::size_t index = 0; index < right.ids[row].size(); ++index) {
                b += right.coefficients[row][index] * coordinates.at(static_cast<std::size_t>(right.ids[row][index]))[axis];
            }
            maximum = std::max(maximum, std::abs(a - b));
        }
    }
    return maximum;
}

int self_test() {
    if (!(std::isfinite(kValidationOnlySentinel) && kValidationOnlySentinel > 0.0)) {
        throw std::runtime_error("validation-only sample sentinel rejected");
    }
    RefinerPtr refiner = make_tetrahedron_refiner();
    if (!refiner) {
        throw std::runtime_error("base TopologyRefiner construction failed");
    }
    Rows const bfr = evaluate_bfr(*refiner, 0.25, 0.25);
    validate_rows(bfr, "Bfr");
    Rows const far = evaluate_far(*refiner, 0.25, 0.25);
    validate_rows(far, "Far");
    double const spread = maximum_geometry_spread(bfr, far);
    if (!std::isfinite(spread)) {
        throw std::runtime_error("nonfinite inter-method spread");
    }
    std::cout << std::setprecision(17)
              << "{\"schema_version\":1,\"kind\":\"bfr_candidate_self_test\","
              << "\"status\":\"ok\",\"finite\":true,"
              << "\"opensubdiv_version\":" << OPENSUBDIV_VERSION_NUMBER << ","
              << "\"topology_refiner_shared\":true,"
              << "\"bfr_role\":\"qualification_target\","
              << "\"far_role\":\"regression_comparator_only\","
              << "\"sample_weight_use\":\"validation_only_not_quadrature\","
              << "\"observed_inter_method_spread\":" << spread << ","
              << "\"spread_is_accuracy_floor\":false,"
              << "\"near_vertex_ranking_declined\":true,"
              << "\"d9a_decided\":false,\"d9b_decided\":false}\n";
    return 0;
}

int preflight(char const *meshDirectory, char const *mutation) {
    if (std::fesetround(FE_TONEAREST) != 0 || std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("FE_TONEAREST could not be established");
    }
    b2fixture::Mesh mesh = b2fixture::read_mesh(meshDirectory);
    b2fixture::apply_mutation(mesh, mutation);
    b2fixture::validate_closed_oriented_two_manifold(mesh);
    RefinerPtr refiner = make_mesh_refiner(mesh);
    std::cout << "{\"schema_version\":1,\"kind\":\"bfr_fixture_preflight\","
              << "\"status\":\"ok\",\"finite\":true,\"candidate_objects_constructed\":1,"
              << "\"rows_emitted\":0,\"vertex_count\":" << mesh.vertices.size() << ","
              << "\"face_count\":" << mesh.faces.size() << ",\"valences\":[";
    for (std::size_t index = 0; index < mesh.valences.size(); ++index) {
        if (index) std::cout << ',';
        std::cout << mesh.valences[index];
    }
    std::cout << "]}\n";
    return 0;
}

void emit_int_array(std::ostream &output, std::vector<int> const &values) {
    output << '[';
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index) output << ',';
        output << values[index];
    }
    output << ']';
}

void emit_double_array(std::ostream &output, std::vector<double> const &values) {
    output << '[' << std::setprecision(17);
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index) output << ',';
        if (!std::isfinite(values[index])) throw std::runtime_error("nonfinite row serialization");
        output << values[index];
    }
    output << ']';
}

Preparation prepare_numeric_case(b2fixture::Mesh const &mesh,
                                 std::string const &candidate, int level,
                                 std::string const &mode, RssLedger *rss) {
    if (candidate == "bfr") return prepare_bfr_case(mesh, level, mode, rss);
    if (candidate == "far" && mode == "not_applicable_uncached") {
        return prepare_far_case(mesh, level, rss);
    }
    throw std::runtime_error("candidate/mode pairing violates the frozen protocol");
}

void destroy_preparation(Preparation &preparation, RssLedger *rss) {
    preparation.package.reset();
    observe_named_rss(rss, &RssLedger::afterRowPackageDestruction);
    preparation.bfrFactory.reset();
    preparation.farTable.reset();
    observe_named_rss(rss, &RssLedger::afterFactoryOrCacheDestruction);
    preparation.refiner.reset();
    observe_named_rss(rss, &RssLedger::afterRefinerDestruction);
}

std::string binary64_bits_hex(double value) {
    std::ostringstream stream;
    stream << std::hex << std::setfill('0') << std::setw(16)
           << b2fixture::bits(value);
    return stream.str();
}

int execute_case(char const *meshDirectory, char const *mutation,
                 std::string const &candidate, int level,
                 std::string const &mode, char const *contentIdentity) {
    if (level < 2 || level > 8) throw std::runtime_error("approximation level outside frozen sweep");
    if (std::fesetround(FE_TONEAREST) != 0 || std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("FE_TONEAREST could not be established");
    }
    b2fixture::Mesh mesh = b2fixture::read_mesh(meshDirectory);
    b2fixture::apply_mutation(mesh, mutation);
    b2fixture::validate_closed_oriented_two_manifold(mesh);
    RssLedger rss;
    rss.baseline = resident_bytes();
    std::vector<std::uint64_t> measured;
    std::size_t measuredRowGroupCount = 0;
    for (int repeat = 0; repeat < 18; ++repeat) {
        Preparation preparation = prepare_numeric_case(mesh, candidate, level, mode, &rss);
        if (!preparation.package) throw std::runtime_error("numeric row package missing");
        if (repeat == 0) measuredRowGroupCount = preparation.package->groups.size();
        if (preparation.package->groups.size() != measuredRowGroupCount) {
            throw std::runtime_error("numeric repeat row-group count drift");
        }
        if (repeat >= 3) measured.push_back(preparation.elapsedNanoseconds);
        destroy_preparation(preparation, &rss);
    }
    if (measured.size() != 15 || measuredRowGroupCount == 0) {
        throw std::runtime_error("numeric repeat lifecycle incomplete");
    }
    bool const rssComplete =
        rss.afterRefinerConstruction == 18 &&
        rss.afterFactoryOrCacheConstruction == 18 &&
        rss.afterEachCompletedFaceRowInsertion == 18 * measuredRowGroupCount &&
        rss.afterImmutablePackagePublication == 18 &&
        rss.afterRowPackageDestruction == 18 &&
        rss.afterFactoryOrCacheDestruction == 18 &&
        rss.afterRefinerDestruction == 18;
    std::uint64_t const expectedRssSamples =
        UINT64_C(18) * (static_cast<std::uint64_t>(measuredRowGroupCount) + UINT64_C(6));
    std::uint64_t const actualRssSamples =
        rss.afterRefinerConstruction + rss.afterFactoryOrCacheConstruction +
        rss.afterEachCompletedFaceRowInsertion + rss.afterImmutablePackagePublication +
        rss.afterRowPackageDestruction + rss.afterFactoryOrCacheDestruction +
        rss.afterRefinerDestruction;
    if (!rssComplete || actualRssSamples != expectedRssSamples) {
        throw std::runtime_error("MEASUREMENT_PROTOCOL_FAILURE_RSS_BOUNDARY_COUNT");
    }

    // Complete row JSON is generated by a separate replay.  It is deliberately
    // outside all 18 preparation timings and all D12 RSS observations.
    Preparation serialization = prepare_numeric_case(mesh, candidate, level, mode, nullptr);
    if (!serialization.package ||
        serialization.package->groups.size() != measuredRowGroupCount) {
        throw std::runtime_error("untimed serialization replay coverage drift");
    }
    RowPackage const &package = *serialization.package;
    std::vector<std::uint64_t> ordered = measured;
    std::sort(ordered.begin(), ordered.end());
    static char const *rowNames[kRowCount] = {"position", "du", "dv", "duu", "duv", "dvv"};
    std::ostringstream output;
    output << std::setprecision(17)
              << "{\"schema_version\":1,\"kind\":\"bfr_candidate_case\",\"status\":\"ok\","
              << "\"finite\":true,\"content_identity_key\":\"" << contentIdentity << "\","
              << "\"candidate\":\"" << candidate << "\",\"approximation_level\":" << level << ','
              << "\"applicable_mode\":\"" << mode << "\",\"warmup_count\":3,"
              << "\"preparation_ns\":[";
    for (std::size_t index = 0; index < measured.size(); ++index) {
        if (index) output << ',';
        output << measured[index];
    }
    output << "],\"preparation_median_ns\":" << ordered[7]
              << ",\"peak_rss_delta_bytes\":" << rss.peakDeltaBytes
              << ",\"rss_baseline_sample_count\":1"
              << ",\"rss_named_sample_count\":" << actualRssSamples
              << ",\"rss_expected_named_sample_count\":" << expectedRssSamples
              << ",\"rss_named_samples_complete\":" << (rssComplete ? "true" : "false")
              << ",\"rss_named_sample_counts\":{"
              << "\"after_refiner_construction\":" << rss.afterRefinerConstruction
              << ",\"after_factory_or_cache_construction\":" << rss.afterFactoryOrCacheConstruction
              << ",\"after_each_completed_face_row_insertion\":" << rss.afterEachCompletedFaceRowInsertion
              << ",\"after_immutable_package_publication\":" << rss.afterImmutablePackagePublication
              << ",\"after_row_package_destruction\":" << rss.afterRowPackageDestruction
              << ",\"after_factory_or_cache_destruction\":" << rss.afterFactoryOrCacheDestruction
              << ",\"after_refiner_destruction\":" << rss.afterRefinerDestruction << '}'
              << ",\"untimed_serialization_replay\":true"
              << ",\"serialization_replay_rss_sampled\":false"
              << ",\"retained_payload_bytes_per_face\":"
              << package.maxRetainedPayloadPerFace
              << ",\"row_group_count\":" << package.groups.size()
              << ",\"max_row_sum_error\":" << package.maxRowSumError
              << ",\"source_reconstruction_complete\":true,\"row_kind_counts\":{";
    for (int row = 0; row < kRowCount; ++row) {
        if (row) output << ',';
        output << '\"' << rowNames[row] << "\":" << package.groups.size();
    }
    output << "},\"rows\":[";
    bool first = true;
    for (std::size_t groupIndex = 0; groupIndex < package.groups.size(); ++groupIndex) {
        RowGroup const &group = package.groups[groupIndex];
        for (int row = 0; row < kRowCount; ++row) {
            if (!first) output << ',';
            first = false;
            output << "{\"content_identity_key\":\"" << contentIdentity << "\""
                      << ",\"candidate\":\"" << candidate << "\""
                      << ",\"approximation_level\":" << level
                      << ",\"applicable_mode\":\"" << mode << "\""
                      << ",\"face_row\":" << group.face
                      << ",\"local_corner_or_none\":" << group.sample.localCorner
                      << ",\"sample_id\":\"" << group.sample.id << "\","
                      << "\"u_binary64\":" << group.sample.u << ",\"v_binary64\":" << group.sample.v
                      << ",\"u_binary64_bits_hex\":\"" << binary64_bits_hex(group.sample.u) << "\""
                      << ",\"v_binary64_bits_hex\":\"" << binary64_bits_hex(group.sample.v) << "\""
                      << ",\"weight_bits_hex\":\"3ff0000000000000\",\"row_kind\":\""
                      << rowNames[row] << "\",\"source_ids\":";
            emit_int_array(output, group.rows.ids[row]);
            output << ",\"coefficients\":";
            emit_double_array(output, group.rows.coefficients[row]);
            output << '}';
        }
    }
    output << "]}\n";
    std::string const rendered = output.str();
    destroy_preparation(serialization, nullptr);
    std::cout << rendered;
    return 0;
}

void append_u32(std::vector<unsigned char> &bytes, std::uint32_t value) {
    for (int shift = 0; shift < 32; shift += 8) {
        bytes.push_back(static_cast<unsigned char>((value >> shift) & 0xffU));
    }
}

void append_u64(std::vector<unsigned char> &bytes, std::uint64_t value) {
    for (int shift = 0; shift < 64; shift += 8) {
        bytes.push_back(static_cast<unsigned char>((value >> shift) & UINT64_C(0xff)));
    }
}

std::vector<unsigned char> canonical_package_bytes(RowPackage const &package) {
    static char const magic[] = "B2ROWV1";
    std::vector<unsigned char> bytes;
    for (std::size_t groupIndex = 0; groupIndex < package.groups.size(); ++groupIndex) {
        RowGroup const &group = package.groups[groupIndex];
        for (int row = 0; row < kRowCount; ++row) {
            bytes.insert(bytes.end(), magic, magic + 7);
            append_u32(bytes, static_cast<std::uint32_t>(group.face));
            append_u32(bytes, static_cast<std::uint32_t>(group.sample.id.size()));
            bytes.insert(bytes.end(), group.sample.id.begin(), group.sample.id.end());
            append_u32(bytes, static_cast<std::uint32_t>(row));
            append_u32(bytes, static_cast<std::uint32_t>(group.rows.ids[row].size()));
            for (std::size_t index = 0; index < group.rows.ids[row].size(); ++index) {
                append_u32(bytes, static_cast<std::uint32_t>(group.rows.ids[row][index]));
                std::uint64_t coefficientBits = 0;
                std::memcpy(&coefficientBits, &group.rows.coefficients[row][index],
                            sizeof(coefficientBits));
                append_u64(bytes, coefficientBits);
            }
        }
    }
    return bytes;
}

class StartBarrier {
public:
    explicit StartBarrier(int participants) : participants_(participants), waiting_(0), generation_(0) {}
    void wait() {
        std::unique_lock<std::mutex> lock(mutex_);
        int const generation = generation_;
        if (++waiting_ == participants_) {
            waiting_ = 0;
            ++generation_;
            condition_.notify_all();
        } else {
            condition_.wait(lock, [this, generation]() { return generation_ != generation; });
        }
    }
private:
    int participants_;
    int waiting_;
    int generation_;
    std::mutex mutex_;
    std::condition_variable condition_;
};

int thread_case(char const *meshDirectory, char const *mutation, int level,
                std::string const &mode, int workerCount, char const *contentIdentity) {
    if (level < 2 || level > 8 || (workerCount != 1 && workerCount != 2 && workerCount != 4)) {
        throw std::runtime_error("thread tuple outside frozen matrix");
    }
    if (std::fesetround(FE_TONEAREST) != 0 || std::fegetround() != FE_TONEAREST) {
        throw std::runtime_error("FE_TONEAREST could not be established");
    }
    b2fixture::Mesh mesh = b2fixture::read_mesh(meshDirectory);
    b2fixture::apply_mutation(mesh, mutation);
    b2fixture::validate_closed_oriented_two_manifold(mesh);
    RefinerPtr refiner = make_mesh_refiner(mesh);
    Bfr::SurfaceFactory::Options options;
    options.EnableCaching(mode != "cache_disabled");
    options.SetApproxLevelSmooth(level);
    options.SetApproxLevelSharp(6);
    typedef Bfr::SurfaceFactoryCacheThreaded<
        std::mutex, std::lock_guard<std::mutex>, std::lock_guard<std::mutex> > ThreadedCache;
    std::unique_ptr<Bfr::RefinerSurfaceFactoryBase> factory;
    if (mode == "cache_disabled") {
        factory.reset(new Bfr::RefinerSurfaceFactory<>(*refiner, options));
    } else if (mode == "SurfaceFactoryCacheThreaded") {
        factory.reset(new Bfr::RefinerSurfaceFactory<ThreadedCache>(*refiner, options));
    } else {
        throw std::runtime_error("thread cache mode outside frozen matrix");
    }
    std::vector<unsigned char> reference;
    std::uint64_t canonicalByteCount = 0;
    for (int round = 0; round < 20; ++round) {
        StartBarrier barrier(workerCount);
        std::vector<std::vector<unsigned char> > results(static_cast<std::size_t>(workerCount));
        std::vector<std::exception_ptr> errors(static_cast<std::size_t>(workerCount));
        std::vector<std::thread> workers;
        workers.reserve(static_cast<std::size_t>(workerCount));
        for (int worker = 0; worker < workerCount; ++worker) {
            workers.push_back(std::thread([&, worker]() {
                try {
                    barrier.wait();
                    std::unique_ptr<RowPackage> package =
                        build_bfr_workload(mesh, *factory, nullptr);
                    results[static_cast<std::size_t>(worker)] =
                        canonical_package_bytes(*package);
                } catch (...) {
                    errors[static_cast<std::size_t>(worker)] = std::current_exception();
                }
            }));
        }
        for (std::size_t worker = 0; worker < workers.size(); ++worker) workers[worker].join();
        for (std::size_t worker = 0; worker < errors.size(); ++worker) {
            if (errors[worker]) std::rethrow_exception(errors[worker]);
        }
        for (int worker = 1; worker < workerCount; ++worker) {
            if (results[static_cast<std::size_t>(worker)] != results[0]) {
                throw std::runtime_error("thread workers emitted different canonical rows");
            }
        }
        if (round == 0) {
            reference = results[0];
            canonicalByteCount = reference.size();
        } else if (results[0] != reference) {
            throw std::runtime_error("thread rounds emitted different canonical rows");
        }
    }
    std::cout << "{\"schema_version\":1,\"kind\":\"bfr_thread_case\",\"status\":\"ok\","
              << "\"finite\":true,\"content_identity_key\":\"" << contentIdentity << "\","
              << "\"approxLevelSmooth\":" << level << ",\"mode\":\"" << mode << "\","
              << "\"worker_count\":" << workerCount << ",\"rounds\":20,"
              << "\"canonical_rows_identical\":true,\"concurrent_factory_mode\":\""
              << mode << "\",\"canonical_byte_count\":" << canonicalByteCount << "}\n";
    return 0;
}

}  // namespace

int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--self-test") {
            return self_test();
        }
        if (argc == 2 && std::string(argv[1]) == "--platform-probe") {
            return platform_probe();
        }
        if (argc == 4 && std::string(argv[1]) == "--preflight") {
            return preflight(argv[2], argv[3]);
        }
        if (argc == 8 && std::string(argv[1]) == "--execute-case") {
            return execute_case(argv[2], argv[3], argv[4], std::atoi(argv[5]), argv[6], argv[7]);
        }
        if (argc == 8 && std::string(argv[1]) == "--thread-case") {
            return thread_case(argv[2], argv[3], std::atoi(argv[4]), argv[5],
                               std::atoi(argv[6]), argv[7]);
        }
        std::cerr << "usage: bfr_candidate --self-test | --platform-probe | "
                     "--preflight MESH_DIR MUTATION | "
                     "--execute-case MESH_DIR MUTATION CANDIDATE LEVEL MODE CONTENT_ID\n";
        return 2;
    } catch (std::exception const &error) {
        std::cerr << error.what() << "\n";
        return 3;
    }
}
