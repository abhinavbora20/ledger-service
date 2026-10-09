from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_session
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token
from app.users import authenticate, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, session: Session = Depends(get_session)):
    user = register_user(session, body.email, body.password)
    result = UserOut(id=user.id, email=user.email)
    session.commit()
    return result


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, session: Session = Depends(get_session)):
    user = authenticate(session, body.email, body.password)
    return TokenOut(access_token=create_access_token(user.id))
