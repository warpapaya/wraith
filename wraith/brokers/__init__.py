"""Data broker opt-out modules."""

from wraith.brokers.base import BrokerBase, SubmissionResult
from wraith.brokers.fastpeoplesearch import FastPeopleSearch
from wraith.brokers.whitepages import Whitepages
from wraith.brokers.spokeo import Spokeo
from wraith.brokers.beenverified import BeenVerified
from wraith.brokers.intelius import Intelius
from wraith.brokers.peoplefinder import PeopleFinder
from wraith.brokers.truthfinder import TruthFinder
from wraith.brokers.mylife import MyLife
from wraith.brokers.checkpeople import CheckPeople
from wraith.brokers.usphonebook import USPhoneBook
from wraith.brokers.radaris import Radaris
from wraith.brokers.instantcheckmate import InstantCheckMate
from wraith.brokers.thatsthem import ThatsThem

ALL_BROKERS: list[type[BrokerBase]] = [
    FastPeopleSearch,
    Whitepages,
    Spokeo,
    BeenVerified,
    Intelius,
    PeopleFinder,
    TruthFinder,
    MyLife,
    CheckPeople,
    USPhoneBook,
    Radaris,
    InstantCheckMate,
    ThatsThem,
]

BROKER_MAP: dict[str, type[BrokerBase]] = {b.name: b for b in ALL_BROKERS}

__all__ = [
    "BrokerBase",
    "SubmissionResult",
    "ALL_BROKERS",
    "BROKER_MAP",
]
