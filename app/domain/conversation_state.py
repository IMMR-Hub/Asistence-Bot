from __future__ import annotations

from enum import Enum
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class ConversationState(str, Enum):
    NEW = "new"
    COLLECTING_IDENTITY = "collecting_identity"
    URGENT_ESCALATED_WAITING = "urgent_escalated_waiting"
    BOOKING_COLLECTING_PREFERENCE = "booking_collecting_preference"
    BOOKING_OFFERING_SLOTS = "booking_offering_slots"
    BOOKING_WAITING_CONFIRMATION = "booking_waiting_confirmation"
    BOOKED = "booked"
    CLOSED = "closed"


class LastQuestion(str, Enum):
    NONE = "none"
    ASK_IDENTITY = "ask_identity"
    ASK_CONTACT = "ask_contact"
    ASK_TIME_PREFERENCE = "ask_time_preference"
    OFFER_SLOTS = "offer_slots"
    ASK_BOOKING_CONFIRMATION = "ask_booking_confirmation"
    INFORM_ESCALATION = "inform_escalation"


class LastAction(str, Enum):
    NONE = "none"
    REQUESTED_IDENTITY = "requested_identity"
    REQUESTED_CONTACT = "requested_contact"
    OFFERED_TIME_PREFERENCE = "offered_time_preference"
    OFFERED_SLOTS = "offered_slots"
    REQUESTED_BOOKING_CONFIRMATION = "requested_booking_confirmation"
    CONFIRMED_BOOKING = "confirmed_booking"
    ESCALATED_TO_HUMAN = "escalated_to_human"
    MARKED_CLOSED = "marked_closed"


class TimeOfDayPreference(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    ANY = "any"


class EscalationReason(str, Enum):
    URGENT_PAIN = "urgent_pain"
    BLEEDING = "bleeding"
    SWELLING = "swelling"
    FEVER = "fever"
    BROKEN_TOOTH = "broken_tooth"
    HUMAN_REQUEST = "human_request"
    COMPLAINT = "complaint"
    UNKNOWN = "unknown"


class IntentKey(str, Enum):
    UNKNOWN = "unknown"
    GENERAL_FAQ = "general_faq"
    BOOK_APPOINTMENT = "book_appointment"
    BOOK_CLEANING = "book_cleaning"
    PRICE_INQUIRY = "price_inquiry"
    URGENT_PAIN = "urgent_pain"
    HUMAN_ESCALATION = "human_escalation"
    THANKS_ONLY = "thanks_only"
    COMPLAINT = "complaint"


class SlotOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=160)
    iso_datetime: str = Field(min_length=1, max_length=80)
    available: bool = True


class CapturedIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @property
    def has_minimum_for_urgent_escalation(self) -> bool:
        return bool(self.full_name and (self.phone or self.email))

    @property
    def missing_for_urgent_escalation(self) -> list[str]:
        missing: list[str] = []
        if not self.full_name:
            missing.append("full_name")
        if not self.phone and not self.email:
            missing.append("contact")
        return missing


class ConversationMemory(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    state: ConversationState = ConversationState.NEW
    intent: IntentKey = IntentKey.UNKNOWN

    captured_identity: CapturedIdentity = Field(default_factory=CapturedIdentity)

    urgent_escalated: bool = False
    escalation_reason: EscalationReason | None = None

    preferred_time_of_day: TimeOfDayPreference | None = None
    offered_slots: list[SlotOffer] = Field(default_factory=list)
    selected_slot_id: str | None = None
    selected_slot_label: str | None = None
    selected_slot_iso_datetime: str | None = None

    last_question_asked: LastQuestion = LastQuestion.NONE
    last_action: LastAction = LastAction.NONE

    assistant_intro_done: bool = False
    awaiting_human_callback: bool = False
    no_reply_terminal: bool = False

    last_user_question_type: str | None = None
    last_meaningful_user_message: str | None = None
    last_assistant_template_key: str | None = None

    tags: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=1000)

    @property
    def is_terminal(self) -> bool:
        return self.state in {ConversationState.BOOKED, ConversationState.CLOSED}

    @property
    def can_go_silent_on_thanks(self) -> bool:
        return self.no_reply_terminal or self.state in {
            ConversationState.BOOKED,
            ConversationState.CLOSED,
            ConversationState.URGENT_ESCALATED_WAITING,
        }

    @property
    def has_selected_slot(self) -> bool:
        return bool(self.selected_slot_id and self.selected_slot_label and self.selected_slot_iso_datetime)

    @model_validator(mode="after")
    def validate_consistency(self) -> "ConversationMemory":
        if self.urgent_escalated and self.state not in {
            ConversationState.URGENT_ESCALATED_WAITING,
            ConversationState.CLOSED,
        }:
            raise ValueError("urgent_escalated only allowed with urgent_escalated_waiting or closed states")

        if self.has_selected_slot and self.state not in {
            ConversationState.BOOKING_WAITING_CONFIRMATION,
            ConversationState.BOOKED,
        }:
            raise ValueError("selected slot only allowed in booking_waiting_confirmation or booked states")

        if self.state == ConversationState.BOOKING_OFFERING_SLOTS and not self.offered_slots:
            raise ValueError("booking_offering_slots requires at least one offered slot")

        if self.state == ConversationState.BOOKED and not self.has_selected_slot:
            raise ValueError("booked requires a selected slot")

        if self.awaiting_human_callback and not self.urgent_escalated:
            raise ValueError("awaiting_human_callback requires urgent_escalated")

        return self


class TransitionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    next_state: ConversationState
    reason: str = Field(min_length=1, max_length=500)
    set_last_question: LastQuestion = LastQuestion.NONE
    set_last_action: LastAction = LastAction.NONE
    no_reply: bool = False
    patch: dict[str, Any] = Field(default_factory=dict)


class ConversationStateEngine:
    TERMINAL_THANKS = {
        "gracias",
        "muchas gracias",
        "ok gracias",
        "dale gracias",
        "perfecto gracias",
        "genial gracias",
    }

    BOOKING_CONFIRMATIONS = {
        "sí",
        "si",
        "confirmo",
        "dale",
        "perfecto",
        "me sirve",
        "ok",
        "está bien",
        "esta bien",
    }

    @staticmethod
    def normalize_text(text: str) -> str:
        return " ".join(text.strip().lower().split())

    @classmethod
    def is_terminal_thanks(cls, text: str) -> bool:
        return cls.normalize_text(text) in cls.TERMINAL_THANKS

    @classmethod
    def is_booking_confirmation(cls, text: str) -> bool:
        normalized = cls.normalize_text(text)
        # Exact match first (most precise)
        if normalized in cls.BOOKING_CONFIRMATIONS:
            return True
        # Substring: "sí, confirmo" or "dale, me sirve" should also match
        return any(word in normalized for word in cls.BOOKING_CONFIRMATIONS)

    @staticmethod
    def choose_time_preference(text: str) -> TimeOfDayPreference | None:
        normalized = ConversationStateEngine.normalize_text(text)
        morning_markers = {"mañana", "manana", "de mañana", "por la mañana", "temprano"}
        afternoon_markers = {"tarde", "por la tarde", "a la tarde", "primera hora de la tarde"}
        if any(marker in normalized for marker in morning_markers):
            return TimeOfDayPreference.MORNING
        if any(marker in normalized for marker in afternoon_markers):
            return TimeOfDayPreference.AFTERNOON
        return None

    @staticmethod
    def find_selected_slot(text: str, offered_slots: Iterable[SlotOffer]) -> SlotOffer | None:
        normalized = ConversationStateEngine.normalize_text(text)

        import re
        exact_hour = None
        match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\b", normalized)
        if match:
            hour = match.group(1)
            minute = match.group(2) or "00"
            exact_hour = f"{int(hour):02d}:{minute}"

        slots = list(offered_slots)
        if normalized in {"la primera", "primera", "el primero"} and slots:
            return slots[0]
        if normalized in {"la segunda", "segunda", "el segundo"} and len(slots) > 1:
            return slots[1]

        for slot in slots:
            label_normalized = ConversationStateEngine.normalize_text(slot.label)
            if label_normalized in normalized:
                return slot
            if slot.iso_datetime in normalized:
                return slot
            if exact_hour and exact_hour in label_normalized:
                return slot

        if normalized in {"esa", "esa me sirve", "me sirve esa", "ese horario"} and slots:
            return slots[0]

        return None

    def decide(
        self,
        *,
        memory: ConversationMemory,
        latest_user_text: str,
        detected_intent: IntentKey,
    ) -> TransitionDecision:
        normalized = self.normalize_text(latest_user_text)

        if self.is_terminal_thanks(normalized) and memory.can_go_silent_on_thanks:
            return TransitionDecision(
                next_state=memory.state,
                reason="terminal thanks with no further action needed",
                no_reply=True,
                set_last_action=memory.last_action,
                set_last_question=memory.last_question_asked,
            )

        if memory.state == ConversationState.URGENT_ESCALATED_WAITING:
            return TransitionDecision(
                next_state=ConversationState.URGENT_ESCALATED_WAITING,
                reason="urgent case already escalated; keep waiting unless handled elsewhere",
                set_last_action=memory.last_action,
                set_last_question=memory.last_question_asked,
            )

        if detected_intent in {IntentKey.URGENT_PAIN, IntentKey.HUMAN_ESCALATION, IntentKey.COMPLAINT}:
            if memory.captured_identity.has_minimum_for_urgent_escalation:
                return TransitionDecision(
                    next_state=ConversationState.URGENT_ESCALATED_WAITING,
                    reason="urgent flow has enough identity data to escalate",
                    set_last_action=LastAction.ESCALATED_TO_HUMAN,
                    set_last_question=LastQuestion.INFORM_ESCALATION,
                    patch={
                        "urgent_escalated": True,
                        "awaiting_human_callback": True,
                    },
                )

            return TransitionDecision(
                next_state=ConversationState.COLLECTING_IDENTITY,
                reason="urgent flow requires minimum identity before escalation",
                set_last_action=LastAction.REQUESTED_IDENTITY,
                set_last_question=LastQuestion.ASK_IDENTITY,
            )

        return TransitionDecision(
            next_state=memory.state,
            reason="no forced state transition",
            set_last_action=memory.last_action,
            set_last_question=memory.last_question_asked,
        )

    def transition(
        self,
        *,
        memory: ConversationMemory,
        decision: TransitionDecision,
    ) -> ConversationMemory:
        payload = memory.model_dump()
        payload.update(decision.patch)
        payload["state"] = decision.next_state
        payload["last_question_asked"] = decision.set_last_question
        payload["last_action"] = decision.set_last_action
        return ConversationMemory.model_validate(payload)
