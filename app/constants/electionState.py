import enum


class CurrentElectionState(enum.Enum):
    CURRENT_ELECTION_STATE_PENDING_DATE = 'current_election_state_pending_date'
    CURRENT_ELECTION_STATE_REGISTRATION_V0 = 'current_election_state_registration_v0'
    CURRENT_ELECTION_STATE_SEEDING_V0 = 'current_election_state_seeding_v0'
    CURRENT_ELECTION_STATE_INIT_VOTERS_V0 = 'current_election_state_init_voters_v0'
    CURRENT_ELECTION_STATE_ACTIVE = 'current_election_state_active'
    CURRENT_ELECTION_STATE_POST_ROUND = 'current_election_state_post_round'
    CURRENT_ELECTION_STATE_FINAL = 'current_election_state_final'
    CURRENT_ELECTION_STATE_REGISTRATION_V1 = 'current_election_state_registration_v1'
    CURRENT_ELECTION_STATE_SEEDING_V1 = 'current_election_state_seeding_v1'
    CURRENT_ELECTION_STATE_INIT_VOTERS_V1 = 'current_election_state_init_voters_v1'

    # next state is not form contract - it is here to store on database rooms that
    # are waiting to be used when election is live
    CURRENT_ELECTION_STATE_CUSTOM_FREE_GROUPS = 'current_election_state_custom_free_groups'


def ElectionStatusFromKey(value: str) -> CurrentElectionState:
    assert isinstance(value, str), "value must be a string"
    values = [item for item in CurrentElectionState if item.value == value]
    return values[0] if len(values) > 0 else None
