#include "model/Model.hpp"

#include <cmath>

/**
 * @brief Constructor for the OptimizationAlgorithm class.
 *
 * Initializes an instance of the OptimizationAlgorithm class with default settings.
 * Sets usingNCG to true, isNCGstuck to false, and usingRpi to true.
 */
OptimizationAlgorithm::OptimizationAlgorithm()
{
    usingNCG = true;
    isNCGstuck = false;
    usingRpi = true;
}

/**
 * @brief Constructor for the OptimizationAlgorithm class.
 *
 * Initializes an instance of the OptimizationAlgorithm class with default settings.
 * Customize iteration interval, c1, c2, and step threshold.
 * Sets usingNCG to true, isNCGstuck to false, and usingRpi to true.
 */
OptimizationAlgorithm::OptimizationAlgorithm(const int trialIterationInterval,
                                             const double c1,
                                             const double c2,
                                             const double stepThreshold) : trialIterationInterval(trialIterationInterval),
                                                                           c1(c1),
                                                                           c2(c2),
                                                                           stepThreshold(stepThreshold)
{
    usingNCG = true;
    isNCGstuck = false;
    usingRpi = true;
}

/** @brief Reset NCG and Rpi to default.
 *
 * Sets usingNCG to true, isNCGstuck to false, and usingRpi to true.
 */
void OptimizationAlgorithm::reset_NCG_Rpi()
{
    //usingNCG = true;
    isNCGstuck = false;
    usingRpi = true;
    lineSearchStatus = LineSearchStatus::NotStarted;
}

bool OptimizationAlgorithm::is_finite_value(double value) const
{
    return std::isfinite(value);
}

bool OptimizationAlgorithm::is_descent_direction(double forceDotDirection) const
{
    return std::isfinite(forceDotDirection) && forceDotDirection > betaRestartThreshold;
}

double OptimizationAlgorithm::compute_fletcher_reeves_beta(double previousForceNormSquared,
                                                           double currentForceNormSquared) const
{
    if (!std::isfinite(previousForceNormSquared) ||
        !std::isfinite(currentForceNormSquared) ||
        previousForceNormSquared <= betaRestartThreshold ||
        currentForceNormSquared <= betaRestartThreshold)
    {
        return 0.0;
    }

    const double beta = currentForceNormSquared / previousForceNormSquared;
    if (!std::isfinite(beta) || beta < 0.0)
    {
        return 0.0;
    }
    return beta;
}

bool OptimizationAlgorithm::accepts_ncg_wolfe_step(double currentEnergy,
                                                   double newEnergy,
                                                   double stepSize,
                                                   double initialDirectionalDerivative,
                                                   double trialDirectionalDerivative) const
{
    if (!std::isfinite(currentEnergy) ||
        !std::isfinite(newEnergy) ||
        !std::isfinite(stepSize) ||
        !std::isfinite(initialDirectionalDerivative) ||
        !std::isfinite(trialDirectionalDerivative) ||
        stepSize <= 0.0 ||
        initialDirectionalDerivative >= 0.0)
    {
        return false;
    }

    return newEnergy <= currentEnergy + c1 * stepSize * initialDirectionalDerivative &&
           std::abs(trialDirectionalDerivative) <= c2 * std::abs(initialDirectionalDerivative);
}

bool OptimizationAlgorithm::accepts_simple_energy_decrease(double currentEnergy,
                                                           double newEnergy,
                                                           double trialForceNormSquared) const
{
    return std::isfinite(currentEnergy) &&
           std::isfinite(newEnergy) &&
           std::isfinite(trialForceNormSquared) &&
           newEnergy < currentEnergy;
}

const char *OptimizationAlgorithm::line_search_status_string() const
{
    switch (lineSearchStatus)
    {
    case LineSearchStatus::NotStarted:
        return "not started";
    case LineSearchStatus::AcceptedNcgWolfe:
        return "accepted NCG Wolfe step";
    case LineSearchStatus::AcceptedSimpleDecrease:
        return "accepted simple energy decrease";
    case LineSearchStatus::ConvergedZeroGradient:
        return "converged zero gradient";
    case LineSearchStatus::FailedNonFinite:
        return "failed non-finite value";
    case LineSearchStatus::FailedStepTooSmall:
        return "failed step too small";
    case LineSearchStatus::FailedUphillDirection:
        return "failed uphill direction";
    }
    return "unknown";
}

/**
 * @brief Disables the use of NCG if it has been stuck consecutively over a threshold.
 *
 * If the NCG optimizer has been stuck for too many consecutive iterations (as determined by the `isNCGstuck` flag),
 * this function will increment a counter `nConsecutiveNcgStuck`. If that counter exceeds a threshold of nConsecutiveNcgStuckThreshold, the `usingNCG`
 * flag will be set to false, indicating that NCG should not be used. Otherwise, `usingNCG` remains true.
 *
 * If the NCG optimizer is not currently stuck, the `nConsecutiveNcgStuck` counter is reset to 0 and `usingNCG` is set to
 * true.
 *
 * @return True if NCG should be used, false otherwise.
 */
bool OptimizationAlgorithm::disable_NCG_if_stuck_consecutively()
{
    if (isNCGstuck) {
        nConsecutiveNcgStuck++;
        if (nConsecutiveNcgStuck > nConsecutiveNcgStuckThreshold){
            std::cout << "[OptimizationAlgorithm::disable_NCG_if_stuck_consecutively] Disabled NCG"
            << std::endl;
            usingNCG = false;
        } else {
            usingNCG = true;
        }
    }
    else{
        nConsecutiveNcgStuck = 0;
        //usingNCG = true;
    }
    return usingNCG;
}
