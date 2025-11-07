from sqlalchemy.orm.relationships import _RelationshipDeclared, RelationshipProperty
from app import app, db

from sqlalchemy import Column, ColumnElement, Integer, String, Boolean, JSON, ForeignKey, DateTime, Time
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

import random
import datetime as dt
from datetime import datetime, time
from typing import Any, cast, Optional
from enum import IntEnum


class ActionType(IntEnum):
    RIGHT_ANSWER = 100
    WRONG_ANSWER = 101
    SKIP = 102
    SAVE_WORD = 103


class Word(db.Model):
    __tablename__: str = 'word'

    id: Column[int] = Column(Integer, primary_key=True)

    word: Column[str] = Column(String(128), unique=True, nullable=False)
    missing_part_index: Column[int] = Column(Integer, nullable=False)
    explanation: Column[str] = Column(String(2048))
    answers: Column[list] = Column(JSON, nullable=False)
    right_answer: Column[str] = Column(String(128), nullable=False)

    task_number: Column[int] = Column(Integer)
    category_id: Column[int] = Column(Integer, ForeignKey('category.id'), nullable=True)
    category: _RelationshipDeclared[Any] = relationship('Category', back_populates='words')
    mistake: Column[bool] = Column(Boolean, default=False)

    created_at: Column[datetime] = Column(DateTime, default=datetime.now)
    updated_at: Column[datetime] = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:
        return f"<Word(id={self.id} word='{self.word}')>"


class Category(db.Model):
    __tablename__: str = 'category'

    id: Column[int] = Column(Integer, primary_key=True)
    name: Column[str] = Column(String(128), unique=True, nullable=False)
    words: _RelationshipDeclared[list[Word]] = relationship('Word', back_populates='category', lazy='dynamic')


class Action(db.Model):
    __tablename__: str = 'action'
    
    id: Column[int] = Column(Integer, primary_key=True)
    user_id: Column[int] = Column(Integer, ForeignKey('user.id'), nullable=False, index=True)
    word_id: Column[int] = Column(Integer, ForeignKey('word.id'), nullable=True, index=True)
    action: Column[int] = Column(Integer, nullable=False)
    datetime: Column[dt.datetime] = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    
    # Relationships
    user: _RelationshipDeclared['User'] = relationship('User', back_populates='actions')
    word: _RelationshipDeclared[Optional['Word']] = relationship('Word', backref='actions')
    
    def __repr__(self) -> str:
        return f"<Action(id={self.id}, user_id={self.user_id}, action={self.action})>"


class User(db.Model):
    __tablename__ = 'user'
    
    id: Column[int] = Column(Integer, primary_key=True)
    telegram_id: Column[int] = Column(Integer, unique=True, nullable=True, index=True) 
    created_at: Column[dt.datetime] = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    
    # Relationships
    actions: _RelationshipDeclared[list['Action']] = relationship('Action', back_populates='user', lazy='dynamic')
    settings: _RelationshipDeclared[Optional['Settings']] = relationship('Settings', back_populates='user', uselist=False)
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id})>"


class Settings(db.Model):
    __tablename__ = 'settings'
    
    user_id: Column[int] = Column(Integer, ForeignKey('user.id'), primary_key=True)
    strike: Column[bool] = Column(Boolean, default=True, nullable=False)
    notification: Column[bool] = Column(Boolean, default=False, nullable=False)
    notification_time: Column[time] = Column(Time, nullable=False, default=time(12, 0))
    day_results: Column[bool] = Column(Boolean, nullable=False, default=True)
    day_results_time: Column[time] = Column(Time, nullable=False, default=time(20, 0))
    
    # Relationships
    user: _RelationshipDeclared['User'] = relationship('User', back_populates='settings')
    
    def __repr__(self) -> str:
        return f"<Settings(user_id={self.user_id}, strike={self.strike}, notification={self.notification})>"
