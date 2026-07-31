"""Tests for tournament (taikai) feature."""

from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from taikai.models import Tournament, TournamentMember, TournamentAdmin, TournamentSession
from taikai.services.session_generator import (
    generate_fixed_sessions,
    generate_next_rank_hanchan,
    can_generate_next_rank_hanchan,
)
from taikai.services.calculator import get_tournament_standings, update_session_scores


_test_storages = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


def _score_session(session, base=30000):
    scores = list(session.scores.all())
    data = [
        {'member_id': s.member_id, 'score': base + i * 1000, 'chombo': 0}
        for i, s in enumerate(scores)
    ]
    update_session_scores(session, data)


class SessionGeneratorTestCase(TestCase):
    def setUp(self):
        self.tournament = Tournament.objects.create(
            name='Test Taikai',
            slug='test-taikai',
            session_mode=Tournament.SessionMode.FIXED,
            fixed_hanchan_count=2,
        )
        for name in ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8']:
            TournamentMember.objects.create(tournament=self.tournament, name=name)

    def test_generate_fixed_sessions(self):
        count = generate_fixed_sessions(self.tournament)
        self.assertEqual(count, 4)  # 2 hanchans × 2 tables
        self.assertEqual(
            TournamentSession.objects.filter(name='Hanchan 1 Table 1').count(),
            1,
        )
        session = TournamentSession.objects.get(name='Hanchan 1 Table 1')
        self.assertEqual(session.scores.count(), 4)
        self.assertTrue(all(s.score == 0 for s in session.scores.all()))

    def test_regenerate_fixed_sessions_resets_standings(self):
        generate_fixed_sessions(self.tournament)
        session = TournamentSession.objects.first()
        _score_session(session)
        self.assertTrue(get_tournament_standings(self.tournament))

        generate_fixed_sessions(self.tournament)
        self.assertEqual(get_tournament_standings(self.tournament), [])
        for member in self.tournament.standing_members():
            self.assertEqual(member.total_score.games_played, 0)
            self.assertEqual(member.total_score.total, 0.0)

    def test_substitute_excluded_from_standings(self):
        sub = TournamentMember.objects.create(
            tournament=self.tournament, name='Sub1', is_substitute=True
        )
        generate_fixed_sessions(self.tournament)
        session = TournamentSession.objects.first()
        scores = list(session.scores.all())
        data = [
            {'member_id': s.member_id, 'score': 30000 + i * 1000, 'chombo': 0}
            for i, s in enumerate(scores)
        ]
        update_session_scores(session, data)

        standings = get_tournament_standings(self.tournament)
        self.assertTrue(all(not m.is_substitute for m in standings))

    def test_substitute_excluded_from_session_generation(self):
        sub = TournamentMember.objects.create(
            tournament=self.tournament, name='Sub1', is_substitute=True
        )
        generate_fixed_sessions(self.tournament)
        assigned_ids = set(
            self.tournament.sessions.values_list('scores__member_id', flat=True)
        )
        self.assertNotIn(sub.id, assigned_ids)

    def test_replace_member_with_substitute(self):
        sub = TournamentMember.objects.create(
            tournament=self.tournament, name='Sub1', is_substitute=True
        )
        generate_fixed_sessions(self.tournament)
        session = TournamentSession.objects.first()
        scores = list(session.scores.order_by('pk'))
        replaced = scores[0].member
        data = []
        for i, score_obj in enumerate(scores):
            member_id = sub.id if i == 0 else score_obj.member_id
            data.append({
                'member_id': member_id,
                'score': 30000 + i * 1000,
                'chombo': 0,
            })
        update_session_scores(session, data)

        session.refresh_from_db()
        member_ids = set(session.scores.values_list('member_id', flat=True))
        self.assertIn(sub.id, member_ids)
        self.assertNotIn(replaced.id, member_ids)
        standings = get_tournament_standings(self.tournament)
        self.assertTrue(all(not m.is_substitute for m in standings))


class RankHanchanGeneratorTestCase(TestCase):
    def setUp(self):
        self.tournament = Tournament.objects.create(
            name='Rank Taikai',
            slug='rank-taikai',
            session_mode=Tournament.SessionMode.RANK,
        )
        for name in ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8']:
            TournamentMember.objects.create(tournament=self.tournament, name=name)

    def test_first_rank_hanchan_allowed_with_no_sessions(self):
        allowed, _ = can_generate_next_rank_hanchan(self.tournament)
        self.assertTrue(allowed)

    def test_second_rank_hanchan_blocked_until_first_scored(self):
        generate_next_rank_hanchan(self.tournament)
        allowed, message = can_generate_next_rank_hanchan(self.tournament)
        self.assertFalse(allowed)
        self.assertIn('no zero values', message)

        for session in self.tournament.sessions.filter(hanchan_number=1):
            _score_session(session)

        allowed, _ = can_generate_next_rank_hanchan(self.tournament)
        self.assertTrue(allowed)
        generate_next_rank_hanchan(self.tournament)
        self.assertEqual(
            self.tournament.sessions.filter(hanchan_number=2).count(),
            2,
        )

    def test_fixed_mode_rejects_rank_generation(self):
        tournament = Tournament.objects.create(
            name='Fixed Only',
            slug='fixed-only',
            session_mode=Tournament.SessionMode.FIXED,
            fixed_hanchan_count=1,
        )
        for name in ['A', 'B', 'C', 'D']:
            TournamentMember.objects.create(tournament=tournament, name=name)
        generate_fixed_sessions(tournament)
        allowed, message = can_generate_next_rank_hanchan(tournament)
        self.assertFalse(allowed)
        self.assertIn('Fixed-only', message)


class HybridHanchanGeneratorTestCase(TestCase):
    def setUp(self):
        self.tournament = Tournament.objects.create(
            name='Hybrid Taikai',
            slug='hybrid-taikai',
            session_mode=Tournament.SessionMode.HYBRID,
            fixed_hanchan_count=1,
        )
        for name in ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8']:
            TournamentMember.objects.create(tournament=self.tournament, name=name)

    def test_rank_blocked_until_fixed_hanchan_scored(self):
        generate_fixed_sessions(self.tournament)
        allowed, message = can_generate_next_rank_hanchan(self.tournament)
        self.assertFalse(allowed)
        self.assertIn('no zero values', message)

        for session in self.tournament.sessions.filter(hanchan_number=1):
            _score_session(session)

        allowed, _ = can_generate_next_rank_hanchan(self.tournament)
        self.assertTrue(allowed)
        count = generate_next_rank_hanchan(self.tournament)
        self.assertEqual(count, 2)
        self.assertTrue(
            self.tournament.sessions.filter(
                hanchan_number=2,
                generation_type=TournamentSession.GenerationType.RANK,
            ).exists()
        )


class TournamentViewTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='admin', password='pass')
        self.tournament = Tournament.objects.create(name='View Test', slug='view-test')
        TournamentAdmin.objects.create(user=self.user, tournament=self.tournament)

    @override_settings(STORAGES=_test_storages)
    def test_session_list_public(self):
        for name in ['A', 'B', 'C', 'D']:
            TournamentMember.objects.create(tournament=self.tournament, name=name)
        generate_fixed_sessions(self.tournament)
        response = self.client.get(reverse('taikai:session_list', kwargs={'slug': 'view-test'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sessions')

    @override_settings(STORAGES=_test_storages)
    def test_session_list_member_filter(self):
        members = []
        for name in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
            members.append(TournamentMember.objects.create(tournament=self.tournament, name=name))
        generate_fixed_sessions(self.tournament)
        target = members[0]
        url = reverse('taikai:session_list', kwargs={'slug': 'view-test'})
        response = self.client.get(url, {'member': target.pk})
        self.assertEqual(response.status_code, 200)
        for session in self.tournament.sessions.filter(scores__member=target).distinct():
            self.assertContains(response, session.name)

    @override_settings(STORAGES=_test_storages)
    def test_tournament_detail_shows_admins_and_scoring(self):
        response = self.client.get(reverse('taikai:tournament_detail', kwargs={'slug': 'view-test'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Admins')
        self.assertContains(response, 'Scoring Settings')
        self.assertContains(response, 'admin')
        self.assertContains(response, 'Session Details')

    @override_settings(STORAGES=_test_storages)
    def test_generate_fixed_sessions_requires_admin(self):
        self.client.login(username='admin', password='pass')
        for name in ['A', 'B', 'C', 'D']:
            TournamentMember.objects.create(tournament=self.tournament, name=name)
        response = self.client.post(
            reverse('taikai:generate_sessions', kwargs={'slug': 'view-test'}),
            {'confirm': True},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.tournament.sessions.count(), 3)

    @override_settings(STORAGES=_test_storages)
    def test_generate_rank_hanchan_view(self):
        tournament = Tournament.objects.create(
            name='Rank View',
            slug='rank-view',
            session_mode=Tournament.SessionMode.RANK,
        )
        TournamentAdmin.objects.create(user=self.user, tournament=tournament)
        for name in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
            TournamentMember.objects.create(tournament=tournament, name=name)

        self.client.login(username='admin', password='pass')
        response = self.client.post(
            reverse('taikai:generate_rank_hanchan', kwargs={'slug': 'rank-view'}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(tournament.sessions.count(), 2)
