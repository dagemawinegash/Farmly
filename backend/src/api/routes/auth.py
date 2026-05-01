from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.schemas.auth import (
    AuthResponse,
    LoginRequest,
    PhoneChangeConfirmRequest,
    PhoneChangeConfirmResponse,
    PhoneChangeRequest,
    PhoneChangeRequestedResponse,
    OTPRequestedResponse,
    OTPVerifyResponse,
    RequestOTPRequest,
    SetPasswordRequest,
    UserResponse,
    VerifyOTPRequest,
)
from src.auth.dependencies import get_current_user
from src.auth.jwt_utils import create_access_token, decode_access_token
from src.auth.otp_utils import generate_otp_code, hash_otp, otp_expiry_time, verify_otp_hash
from src.auth.password import hash_password, verify_password
from src.common.utils.phone import normalize_phone
from src.config.settings import get_settings
from src.db.models.user import (
    OTPVerification,
    PhoneChangeVerification,
    User,
    UserProfile,
)
from src.db.session import get_db
from src.integrations.sms.sms_ethiopia import send_sms


router = APIRouter(prefix="/api/auth", tags=["Auth"])
settings = get_settings()


def _to_user_response(user: User) -> UserResponse:
    onboarding_completed = bool(user.profile and user.profile.onboarding_completed)
    return UserResponse(
        user_id=user.user_id,
        phone_number=user.phone_number,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        onboarding_completed=onboarding_completed,
    )


@router.post("/request-otp", response_model=OTPRequestedResponse)
def request_otp(
    payload: RequestOTPRequest,
    db: Session = Depends(get_db),
) -> OTPRequestedResponse:
    try:
        phone_number = normalize_phone(payload.phone_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    existing_user = db.query(User).filter(User.phone_number == phone_number).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number already registered. Please login.",
        )

    db.query(OTPVerification).filter(
        OTPVerification.phone_number == phone_number,
        OTPVerification.consumed.is_(False),
    ).update({OTPVerification.consumed: True}, synchronize_session=False)

    otp_code = generate_otp_code()
    verification = OTPVerification(
        phone_number=phone_number,
        full_name=payload.full_name.strip(),
        otp_code_hash=hash_otp(phone_number, otp_code),
        expires_at=otp_expiry_time(),
        max_attempts=settings.otp_max_attempts,
    )
    db.add(verification)
    db.commit()

    sms_text = f"Farmly verification code: {otp_code}. Expires in {settings.otp_expire_minutes} minutes."
    debug_otp: str | None = None

    try:
        send_sms(phone_number, sms_text)
    except Exception as exc:
        if settings.debug:
            debug_otp = otp_code
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to send OTP SMS: {exc}",
            )

    if settings.debug and debug_otp is None:
        debug_otp = otp_code

    return OTPRequestedResponse(
        message="OTP sent successfully",
        expires_in_minutes=settings.otp_expire_minutes,
        debug_otp=debug_otp,
    )


@router.post("/verify-otp", response_model=OTPVerifyResponse)
def verify_otp(payload: VerifyOTPRequest, db: Session = Depends(get_db)) -> OTPVerifyResponse:
    try:
        phone_number = normalize_phone(payload.phone_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    record = (
        db.query(OTPVerification)
        .filter(
            OTPVerification.phone_number == phone_number,
            OTPVerification.consumed.is_(False),
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="No OTP request found")

    now = datetime.now(timezone.utc)
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        record.consumed = True
        db.commit()
        raise HTTPException(status_code=400, detail="OTP expired")

    if record.verified:
        raise HTTPException(status_code=400, detail="OTP already verified")

    if record.attempts >= record.max_attempts:
        record.consumed = True
        db.commit()
        raise HTTPException(status_code=429, detail="Maximum OTP attempts exceeded")

    if not verify_otp_hash(phone_number, payload.otp_code, record.otp_code_hash):
        record.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP")

    record.verified = True
    record.verified_at = now
    db.commit()

    setup_token = create_access_token(subject=phone_number, expires_minutes=15)
    return OTPVerifyResponse(
        message="OTP verified successfully",
        setup_token=setup_token,
    )


@router.post("/set-password", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def set_password(payload: SetPasswordRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        phone_number = normalize_phone(payload.phone_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    token_payload = decode_access_token(payload.setup_token)
    if token_payload is None or token_payload.get("sub") != phone_number:
        raise HTTPException(status_code=401, detail="Invalid or expired setup token")

    existing_user = db.query(User).filter(User.phone_number == phone_number).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists. Please login.",
        )

    record = (
        db.query(OTPVerification)
        .filter(
            OTPVerification.phone_number == phone_number,
            OTPVerification.consumed.is_(False),
            OTPVerification.verified.is_(True),
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=400, detail="No verified OTP found for this phone number")

    now = datetime.now(timezone.utc)
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        record.consumed = True
        db.commit()
        raise HTTPException(status_code=400, detail="Verified OTP expired. Request a new OTP.")

    user = User(
        phone_number=phone_number,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.flush()

    profile = UserProfile(
        user_id=user.user_id,
        full_name=record.full_name,
        phone_number=phone_number,
    )
    db.add(profile)
    record.consumed = True

    db.commit()
    db.refresh(user)

    access_token = create_access_token(subject=user.user_id)
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=_to_user_response(user),
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        phone_number = normalize_phone(payload.phone_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    user = db.query(User).filter(User.phone_number == phone_number).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone number or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    access_token = create_access_token(subject=user.user_id)
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=_to_user_response(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return _to_user_response(current_user)


@router.post(
    "/users/me/phone-change/request",
    response_model=PhoneChangeRequestedResponse,
)
def request_phone_change(
    payload: PhoneChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PhoneChangeRequestedResponse:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    try:
        new_phone = normalize_phone(payload.new_phone_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if new_phone == current_user.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New phone number is the same as current phone number",
        )

    existing_user = db.query(User).filter(User.phone_number == new_phone).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number already in use",
        )

    cooldown_cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=settings.phone_change_cooldown_seconds
    )
    recent_request = (
        db.query(PhoneChangeVerification)
        .filter(
            PhoneChangeVerification.user_id == current_user.user_id,
            PhoneChangeVerification.consumed.is_(False),
            PhoneChangeVerification.created_at >= cooldown_cutoff,
        )
        .order_by(PhoneChangeVerification.created_at.desc())
        .first()
    )
    if recent_request:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {settings.phone_change_cooldown_seconds} seconds before requesting another OTP",
        )

    db.query(PhoneChangeVerification).filter(
        PhoneChangeVerification.user_id == current_user.user_id,
        PhoneChangeVerification.consumed.is_(False),
    ).update({PhoneChangeVerification.consumed: True}, synchronize_session=False)

    otp_code = generate_otp_code()
    record = PhoneChangeVerification(
        user_id=current_user.user_id,
        new_phone_number=new_phone,
        otp_code_hash=hash_otp(new_phone, otp_code),
        expires_at=otp_expiry_time(),
        max_attempts=settings.otp_max_attempts,
    )
    db.add(record)
    db.commit()

    sms_text = (
        f"Farmly phone change code: {otp_code}. Expires in {settings.otp_expire_minutes} minutes."
    )
    debug_otp: str | None = None
    try:
        send_sms(new_phone, sms_text)
    except Exception as exc:
        if settings.debug:
            debug_otp = otp_code
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to send OTP SMS: {exc}",
            )

    if settings.debug and debug_otp is None:
        debug_otp = otp_code

    return PhoneChangeRequestedResponse(
        message="Phone change OTP sent successfully",
        expires_in_minutes=settings.otp_expire_minutes,
        debug_otp=debug_otp,
    )


@router.post(
    "/users/me/phone-change/confirm",
    response_model=PhoneChangeConfirmResponse,
)
def confirm_phone_change(
    payload: PhoneChangeConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PhoneChangeConfirmResponse:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    try:
        new_phone = normalize_phone(payload.new_phone_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    existing_user = db.query(User).filter(User.phone_number == new_phone).first()
    if existing_user and existing_user.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number already in use",
        )

    record = (
        db.query(PhoneChangeVerification)
        .filter(
            PhoneChangeVerification.user_id == current_user.user_id,
            PhoneChangeVerification.new_phone_number == new_phone,
            PhoneChangeVerification.consumed.is_(False),
        )
        .order_by(PhoneChangeVerification.created_at.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="No phone-change OTP request found")

    now = datetime.now(timezone.utc)
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        record.consumed = True
        db.commit()
        raise HTTPException(status_code=400, detail="OTP expired")

    if record.attempts >= record.max_attempts:
        record.consumed = True
        db.commit()
        raise HTTPException(status_code=429, detail="Maximum OTP attempts exceeded")

    if not verify_otp_hash(new_phone, payload.otp_code, record.otp_code_hash):
        record.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP")

    current_user.phone_number = new_phone
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.user_id).first()
    if profile:
        profile.phone_number = new_phone

    record.verified = True
    record.verified_at = now
    record.consumed = True

    db.commit()
    db.refresh(current_user)

    return PhoneChangeConfirmResponse(
        message="Phone number changed successfully",
        phone_number=current_user.phone_number,
    )
