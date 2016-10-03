"""
An implementation of the profile connection scan algorithm.

Problem description:
Given
1. a static network for pedestrian routing
2. a temporal network with elementary transit events (accompanied with trip_ids)
3. source stop
4. target stop
5. interval start time
6. interval end time

Compute the pareto optimal departure times (from the source stop) and arrival times (to the target stop).
Considering pareto-optimality the following are beneficial
LATER (greater) departure time
EARLIER (smaller) arrival time

Now, the following departure_time, arrival_time pairs would all be pareto-optimal:
1, 3
3, 4
4, 5

However, e.g. (2, 4) would not be a pareto-optimal (departure_time, arrival_time) pair as it is dominated by (4,5)

while only one link in the static network can be traversed at a time.

Implements
"""
from collections import defaultdict

from gtfspy.routing.models import Connection, ParetoTuple
from gtfspy.routing.node_profile import NodeProfile, IdentityNodeProfile
from gtfspy.routing.abstract_routing_algorithm import AbstractRoutingAlgorithm


class ConnectionScanProfiler(AbstractRoutingAlgorithm):
    """
    Implementation of the profile connection scan algorithm presented in

    http://i11www.iti.uni-karlsruhe.de/extra/publications/dpsw-isftr-13.pdf
    """

    def __init__(self,
                 transit_events,
                 target_stop,
                 start_time,
                 end_time,
                 transfer_margin,
                 walk_network,
                 walk_speed):
        """
        Parameters
        ----------
        transit_events: list[Connection]
            events are assumed to be ordered in increasing departure_time (!)
        target_stop: int
            index of the target stop
        start_time : int
            start time in unixtime seconds
        end_time: int
            end time in unixtime seconds (no new connections will be scanned after this time)
        transfer_margin: int
            required extra margin required for transfers in seconds
        walk_speed: float
            walking speed between stops in meters / second
        walk_network: networkx.Graph
            each edge should have the walking distance as a data attribute ("distance_shape") expressed in meters
        """
        AbstractRoutingAlgorithm.__init__(self)
        self._target = target_stop
        self._connections = transit_events
        self._start_time = start_time
        self._end_time = end_time
        self._transfer_margin = transfer_margin
        self._walk_network = walk_network
        self._walk_speed = walk_speed

        # algorithm internals

        # trip flags:
        self.__trip_min_arrival_time = defaultdict(lambda: float("inf"))

        # initialize stop_profiles
        self._stop_profiles = defaultdict(lambda: NodeProfile())
        self._stop_profiles[self._target] = IdentityNodeProfile()

    def _run(self):
        # if source node in s1:
        latest_dep_time = float("inf")
        connections = self._connections  # list[Connection]
        for connection in connections:
            assert(isinstance(connection, Connection))
            departure_time = connection.departure_time
            assert(departure_time <= latest_dep_time)
            latest_dep_time = departure_time
            arrival_time = connection.arrival_time
            departure_stop = connection.departure_stop
            arrival_stop = connection.arrival_stop
            trip_id = connection.trip_id

            arrival_profile = self._stop_profiles[arrival_stop]  # NodeProfile
            dep_stop_profile = self._stop_profiles[departure_stop]

            earliest_arrival_time = arrival_profile.get_earliest_arrival_time_at_target(arrival_time +
                                                                                        self._transfer_margin)
            trip_arrival_time = self.__trip_min_arrival_time[trip_id]

            min_arrival_time = min(trip_arrival_time, earliest_arrival_time)
            if min_arrival_time == float("inf"):
                continue
            if trip_arrival_time > min_arrival_time:
                self.__trip_min_arrival_time[trip_id] = earliest_arrival_time

            pareto_tuple = ParetoTuple(departure_time, min_arrival_time)
            updated_dep_stop = dep_stop_profile.update_pareto_optimal_tuples(pareto_tuple)

            if updated_dep_stop:
                self._scan_footpaths_to_departure_stop(departure_stop, departure_time, min_arrival_time)

    def _scan_footpaths_to_departure_stop(self, connection_dep_stop, connection_dep_time, arrival_time_target):
        """ A helper method for scanning the footpaths. Updates self._stop_profiles accordingly"""
        for _, neighbor, distance_shape in self._walk_network.edges_iter(nbunch=[connection_dep_stop],
                                                                         data="distance_shape"):
            neighbor_dep_time = connection_dep_time - distance_shape / self._walk_speed
            pt = ParetoTuple(departure_time=neighbor_dep_time, arrival_time_target=arrival_time_target)
            self._stop_profiles[neighbor].update_pareto_optimal_tuples(pt)

    @property
    def stop_profiles(self):
        """
        Returns
        -------
        _stop_profiles : dict[int, AbstractNodeProfile]
            The pareto tuples necessary.
        """
        assert self._has_run
        return self._stop_profiles



