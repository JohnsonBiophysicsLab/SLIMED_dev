#include "energy_force/Valence4_opensubdiv_production_route.hpp"
#include "energy_force/Valence5_opensubdiv_face_loop.hpp"
#include "energy_force/Valence5_opensubdiv_production_route.hpp"
#include "mesh/Mesh.hpp"

#include <cstdlib>
#include <type_traits>

#include <gtest/gtest.h>

namespace
{
using slimed::opensubdiv_valence5_phase2::Valence5Phase2Result;
using slimed::opensubdiv_valence5_phase2::
    evaluate_guarded_valence5_opensubdiv_production_route;
using slimed::opensubdiv_valence5_phase2::
    evaluate_guarded_valence5_production_route;

TEST(OpenSubdivProductionRouteNaming,
     CanonicalAndLegacyValence5SymbolsLinkAndBehaveIdenticallyDefaultOff)
{
    using Route = Valence5Phase2Result (*)(Mesh &);
    static_assert(std::is_same_v<
        decltype(&evaluate_guarded_valence5_opensubdiv_production_route),
        Route>);
    static_assert(std::is_same_v<
        decltype(&evaluate_guarded_valence5_production_route), Route>);

    if (std::getenv("SLIMED_USE_OPENSUBDIV_VALENCE5") != nullptr)
    {
        GTEST_SKIP() << "compatibility check requires the default-off route";
    }
    Param canonicalParam;
    Param legacyParam;
    canonicalParam.VERBOSE_MODE = false;
    legacyParam.VERBOSE_MODE = false;
    Mesh canonicalMesh(canonicalParam);
    Mesh legacyMesh(legacyParam);

    const Valence5Phase2Result canonical =
        evaluate_guarded_valence5_opensubdiv_production_route(canonicalMesh);
    const Valence5Phase2Result legacy =
        evaluate_guarded_valence5_production_route(legacyMesh);

    EXPECT_EQ(canonical.accepted, legacy.accepted);
    EXPECT_EQ(canonical.rejectionReason, legacy.rejectionReason);
    EXPECT_EQ(canonical.productionRouteEnabled,
              legacy.productionRouteEnabled);
    EXPECT_EQ(canonical.actualProductionForcePathExecuted,
              legacy.actualProductionForcePathExecuted);
    EXPECT_EQ(canonical.defaultEvaluatorCaller,
              legacy.defaultEvaluatorCaller);
}

TEST(OpenSubdivProductionRouteNaming,
     CanonicalValence4AndValence5HeadersCompileTogether)
{
    EXPECT_NE(
        &slimed::valence4_route_preflight::
            evaluate_guarded_valence4_opensubdiv_production_route,
        nullptr);
    EXPECT_NE(&evaluate_guarded_valence5_opensubdiv_production_route,
              nullptr);
}
} // namespace
