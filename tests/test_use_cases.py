from datetime import datetime
from src.domain.entities.headcount import Headcount
from src.domain.use_cases.calculate_counts import CalculateCountsUseCase
from src.domain.use_cases.process_checkin import ProcessCheckInUseCase
from src.domain.use_cases.trigger_broadcast import TriggerBroadcastUseCase
from src.domain.use_cases.reschedule_team import RescheduleTeamUseCase

# Dummy implementations of interfaces for testing

class MockDatabase:
    def __init__(self):
        self.count = Headcount(0, 0, 0, datetime.utcnow())
        self.seats = []

    def get_headcount(self):
        return self.count

    def increment_count(self, zone, value):
        if zone == "sanctuary":
            self.count.sanctuary_count += value
        elif zone == "overflow":
            self.count.overflow_count += value
        elif zone == "volunteer":
            self.count.volunteer_count += value
        return self.count

    def reset_counts(self):
        self.count = Headcount(0, 0, 0, datetime.utcnow())
        return self.count

    def get_seating_map(self):
        return self.seats

    def update_seat(self, row_id, seat_id, is_occupied):
        return True

class MockHardware:
    async def connect(self):
        return True
    async def disconnect(self):
        pass
    async def recall_wing_snapshot(self, snapshot_id):
        return True
    async def set_atem_on_air(self, on_air):
        return True
    async def set_camera_recording(self, camera_id, record):
        return True

class MockPCO:
    async def check_in_person(self, person_id, location_id):
        return True
    async def check_out_person(self, checkin_id):
        return True
    async def trigger_autoschedule(self, plan_id, team_id):
        return []

def test_calculate_counts():
    db = MockDatabase()
    use_case = CalculateCountsUseCase(db)
    
    # Test initial state
    assert use_case.get_current_headcount().sanctuary_count == 0
    
    # Test increment
    updated = use_case.increment_zone_count("sanctuary", 5)
    assert updated.sanctuary_count == 5
    
    # Test reset
    reset_counts = use_case.reset_headcount()
    assert reset_counts.sanctuary_count == 0

async def test_process_checkin():
    pco = MockPCO()
    use_case = ProcessCheckInUseCase(pco)
    
    ok = await use_case.execute_checkin("person-123", "loc-456")
    assert ok is True
    
    checkout_ok = await use_case.execute_checkout("ci-789")
    assert checkout_ok is True

async def test_trigger_broadcast():
    hw = MockHardware()
    use_case = TriggerBroadcastUseCase(hw)
    
    success = await use_case.execute_start_broadcast()
    assert success is True
