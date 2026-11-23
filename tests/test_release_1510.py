"""Regression coverage for database handle cleanup and extreme caption width."""
import sqlite3
import re
import unittest
from unittest.mock import patch
from viralcut import db, subtitles


class Release1510Tests(unittest.TestCase):
    def test_database_session_closes_after_success(self):
        connection = sqlite3.connect(':memory:')
        with patch.object(db, 'connect', return_value=connection):
            with db.session() as conn:
                conn.execute('create table sample (id integer)')
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute('select 1')

    def test_database_session_rolls_back_and_closes_after_failure(self):
        connection = sqlite3.connect(':memory:')
        with patch.object(db, 'connect', return_value=connection):
            with self.assertRaisesRegex(ValueError, 'failure'):
                with db.session():
                    raise ValueError('failure')
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute('select 1')

    def test_extra_long_token_is_within_estimated_safe_width(self):
        token = 'W' * 80
        ass = subtitles.build_ass([dict(word=token,start=0,end=2)],0,3,show_hook=False)
        event = next(line for line in ass.splitlines() if line.startswith('Dialogue:'))
        info = subtitles.font_info('montserrat')
        size = int(re.search(r'\\fs(\d+)',event)[1])
        scales = [float(v) for v in re.findall(r'\\fscx([\d.]+)',event)]
        estimated = len(token)*subtitles._char_advance(info,size)*subtitles._SHRINK_RESERVE*max(scales)/100
        self.assertLessEqual(estimated, subtitles._SAFE_WIDTH+1)
