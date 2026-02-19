#pragma once

#include <map>
#include <string>

class TannerGraph;

namespace GraphDiagnostics {

using DegreeDistribution = std::map<int, int>;

DegreeDistribution variableDegreeDistribution(const TannerGraph& graph);
DegreeDistribution checkDegreeDistribution(const TannerGraph& graph);

// Returns shortest cycle length found up to max_cycle_len.
// Returns -1 when no cycle is found within bound.
int estimateGirthBounded(const TannerGraph& graph, int max_cycle_len = 12);

void printDegreeDistribution(const DegreeDistribution& dist,
                             const std::string& label);

} // namespace GraphDiagnostics

