"""Tests for Player model and member linking."""

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError

from teams.models import Team, Member, Player
from teams.services import resolve_player_for_new_member
from accounts.models import TeamAdmin


_test_storages = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


class PlayerModelTestCase(TestCase):
    def setUp(self):
        self.team_a = Team.objects.create(name='Team A', slug='team-a')
        self.team_b = Team.objects.create(name='Team B', slug='team-b')
        self.player = Player.objects.create(name='Alice')
        self.member_a = Member.objects.create(team=self.team_a, name='Alice', player=self.player)

    def test_resolve_player_new_name(self):
        player, needs_confirmation, teams = resolve_player_for_new_member('Bob', self.team_a)
        self.assertFalse(needs_confirmation)
        self.assertEqual(teams, [])
        self.assertEqual(player.name, 'Bob')

    def test_resolve_player_duplicate_needs_confirmation(self):
        player, needs_confirmation, teams = resolve_player_for_new_member('Alice', self.team_b)
        self.assertTrue(needs_confirmation)
        self.assertIsNone(player)
        self.assertEqual(teams, ['Team A'])

    def test_resolve_player_confirm_same(self):
        player, needs_confirmation, teams = resolve_player_for_new_member(
            'Alice', self.team_b, confirm_same_player=True
        )
        self.assertFalse(needs_confirmation)
        self.assertEqual(player, self.player)

    def test_resolve_player_confirm_different(self):
        player, needs_confirmation, teams = resolve_player_for_new_member(
            'Alice', self.team_b, confirm_same_player=False
        )
        self.assertFalse(needs_confirmation)
        self.assertNotEqual(player, self.player)
        self.assertEqual(player.name, 'Alice')


class MemberCreateViewTestCase(TestCase):
    _test_storages = _test_storages

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='admin', password='pass')
        self.team_a = Team.objects.create(name='Team A', slug='team-a')
        self.team_b = Team.objects.create(name='Team B', slug='team-b')
        TeamAdmin.objects.create(user=self.user, team=self.team_b)
        player = Player.objects.create(name='Alice')
        Member.objects.create(team=self.team_a, name='Alice', player=player)

    @override_settings(STORAGES=_test_storages)
    def test_create_member_shows_duplicate_warning(self):
        self.client.login(username='admin', password='pass')
        url = reverse('teams:member_create', kwargs={'slug': self.team_b.slug})
        response = self.client.post(url, {'name': 'Alice', 'display_name': ''})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_duplicate_warning'])
        self.assertEqual(response.context['existing_teams'], ['Team A'])

    def test_create_member_confirm_same_player(self):
        self.client.login(username='admin', password='pass')
        url = reverse('teams:member_create', kwargs={'slug': self.team_b.slug})
        response = self.client.post(url, {
            'name': 'Alice',
            'display_name': '',
            'confirm_same_player': 'yes',
        })
        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(team=self.team_b, name='Alice')
        member_a = Member.objects.get(team=self.team_a, name='Alice')
        self.assertEqual(member.player, member_a.player)

    def test_create_member_confirm_different_player(self):
        self.client.login(username='admin', password='pass')
        url = reverse('teams:member_create', kwargs={'slug': self.team_b.slug})
        response = self.client.post(url, {
            'name': 'Alice',
            'display_name': '',
            'confirm_same_player': 'no',
        })
        self.assertEqual(response.status_code, 302)
        member = Member.objects.get(team=self.team_b, name='Alice')
        member_a = Member.objects.get(team=self.team_a, name='Alice')
        self.assertNotEqual(member.player, member_a.player)


class PlayerDetailViewTestCase(TestCase):
    _test_storages = _test_storages

    def setUp(self):
        self.client = Client()
        self.team_a = Team.objects.create(name='Team A', slug='team-a')
        self.team_b = Team.objects.create(name='Team B', slug='team-b')
        self.player = Player.objects.create(name='Alice')
        Member.objects.create(team=self.team_a, name='Alice', player=self.player)
        Member.objects.create(team=self.team_b, name='Alice', player=self.player)

    @override_settings(STORAGES=_test_storages)
    def test_player_detail_page_loads(self):
        url = reverse('teams:player_detail', kwargs={'pk': self.player.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alice')
        self.assertContains(response, 'Team A')
        self.assertContains(response, 'Team B')


class PlayerUserLinkTestCase(TestCase):
    _test_storages = _test_storages

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='alice', password='pass')
        self.other_user = User.objects.create_user(username='bob', password='pass')
        self.team = Team.objects.create(name='Team A', slug='team-a')
        self.player = Player.objects.create(name='Alice')

    def test_link_player_to_user(self):
        from teams.services import link_player_to_user
        link_player_to_user(self.player, self.user)
        self.player.refresh_from_db()
        self.assertEqual(self.player.user, self.user)

    def test_link_player_rejects_duplicate_user(self):
        from teams.services import link_player_to_user
        Player.objects.create(name='Alice2', user=self.user)
        with self.assertRaises(ValidationError):
            link_player_to_user(self.player, self.user)

    def test_get_claimable_players_for_user(self):
        from teams.services import get_claimable_players_for_user
        Member.objects.create(team=self.team, name='Alice', player=self.player)
        claimable = list(get_claimable_players_for_user(self.user))
        self.assertEqual(len(claimable), 1)
        self.assertEqual(claimable[0], self.player)

    @override_settings(STORAGES=_test_storages)
    def test_admin_assign_via_member_update(self):
        from accounts.models import TeamAdmin
        admin = User.objects.create_user(username='admin', password='pass')
        TeamAdmin.objects.create(user=admin, team=self.team)
        member = Member.objects.create(team=self.team, name='Alice', player=self.player)

        self.client.force_login(admin)
        response = self.client.post(
            reverse('teams:member_update', kwargs={'pk': member.pk}),
            {'name': 'Alice', 'display_name': '', 'linked_username': 'bob'},
        )
        self.assertEqual(response.status_code, 302)
        self.player.refresh_from_db()
        self.assertEqual(self.player.user, self.other_user)
