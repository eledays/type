from sqlalchemy.orm.relationships import _RelationshipDeclared, RelationshipProperty
from app import app, db

from sqlalchemy import Column, ColumnElement, Integer, String, Boolean, JSON, ForeignKey, DateTime, Time, Float, BigInteger
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

    # Relationships
    user_stats: _RelationshipDeclared[list['UserWordStat']] = relationship('UserWordStat', back_populates='word', lazy='dynamic')
    global_stats: _RelationshipDeclared[list['WordGlobalStat']] = relationship('WordGlobalStat', back_populates='word', lazy='dynamic')

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
    telegram_id: Column[int] = Column(BigInteger, unique=True, nullable=True, index=True)
    created_at: Column[dt.datetime] = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    
    # Relationships
    actions: _RelationshipDeclared[list['Action']] = relationship('Action', back_populates='user', lazy='dynamic')
    settings: _RelationshipDeclared[Optional['Settings']] = relationship('Settings', back_populates='user', uselist=False)
    word_stats: _RelationshipDeclared[list['UserWordStat']] = relationship('UserWordStat', back_populates='user', lazy='dynamic')

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


class UserWordStat(db.Model):
    __tablename__ = 'user_word_stat'

    user_id: Column[int] = Column(Integer, ForeignKey('user.id'), primary_key=True)
    word_id: Column[int] = Column(Integer, ForeignKey('word.id'), primary_key=True)

    correct_count: Column[int] = Column(Integer, default=0)
    wrong_count: Column[int] = Column(Integer, default=0)
    skip_count: Column[int] = Column(Integer, default=0)

    success_streak: Column[int] = Column(Integer, default=0)
    last_seen: Column[dt.datetime] = Column(DateTime)
    last_action: Column[int] = Column(Integer)

    time_score: Column[float] = Column(Float, default=1.0, index=True)
    difficulty_score: Column[float] = Column(Float, default=0.0, index=True)

    # Relationships
    user: _RelationshipDeclared['User'] = relationship('User', back_populates='word_stats')
    word: _RelationshipDeclared['Word'] = relationship('Word', back_populates='user_stats')

    def __repr__(self) -> str:
        return f"<UserWordStat(user_id={self.user_id}, word_id={self.word_id}, correct_count={self.correct_count}, wrong_count={self.wrong_count}, skip_count={self.skip_count})>"


class WordGlobalStat(db.Model):
    __tablename__ = 'word_global_stat'

    word_id: Column[int] = Column(Integer, ForeignKey('word.id'), primary_key=True)

    correct_count: Column[int] = Column(Integer, default=0)
    wrong_count: Column[int] = Column(Integer, default=0)
    skip_count: Column[int] = Column(Integer, default=0)

    difficulty_score: Column[float] = Column(Float, default=0.0, index=True)

    # Relationships
    word: _RelationshipDeclared['Word'] = relationship('Word')

    def __repr__(self) -> str:
        return f"<WordGlobalStat(word_id={self.word_id}, correct_count={self.correct_count}, wrong_count={self.wrong_count}, skip_count={self.skip_count})>"