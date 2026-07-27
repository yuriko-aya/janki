from django.test import TestCase
from django.contrib.auth.models import User
from teams.models import Team, Member, Player
from scores.models import RawScore, CalculatedScore
from scores.services.calculator import submit_session_scores, recalculate_member_score, get_session_details


class TieHandlingTestCase(TestCase):
    """Test cases to verify tie handling in placement and Uma calculation."""
    
    def setUp(self):
        """Set up test data."""
        # Create a user and team
        self.user = User.objects.create_user(username='admin', password='password')
        self.team = Team.objects.create(
            name='Test Team',
            slug='test-team',
            target_point=30000,
            uma_first=15,
            uma_second=5,
            uma_third=-5,
            uma_fourth=-15,
            chombo_enabled=True
        )
        
        # Create 4 members
        player_alice = Player.objects.create(name='Alice')
        player_bob = Player.objects.create(name='Bob')
        player_charlie = Player.objects.create(name='Charlie')
        player_diana = Player.objects.create(name='Diana')
        self.alice = Member.objects.create(team=self.team, name='Alice', player=player_alice)
        self.bob = Member.objects.create(team=self.team, name='Bob', player=player_bob)
        self.charlie = Member.objects.create(team=self.team, name='Charlie', player=player_charlie)
        self.diana = Member.objects.create(team=self.team, name='Diana', player=player_diana)
    
    def test_no_ties_normal_placement(self):
        """Test normal placement calculation without ties."""
        score_data = [
            {'member_id': self.alice.id, 'score': 35000, 'chombo': 0},  # 1st
            {'member_id': self.bob.id, 'score': 30000, 'chombo': 0},    # 2nd
            {'member_id': self.charlie.id, 'score': 25000, 'chombo': 0}, # 3rd
            {'member_id': self.diana.id, 'score': 10000, 'chombo': 0},  # 4th
        ]
        
        submit_session_scores('session-1', self.team, score_data)
        
        # Check placements
        alice_score = RawScore.objects.get(member=self.alice, session_id='session-1')
        bob_score = RawScore.objects.get(member=self.bob, session_id='session-1')
        charlie_score = RawScore.objects.get(member=self.charlie, session_id='session-1')
        diana_score = RawScore.objects.get(member=self.diana, session_id='session-1')
        
        self.assertEqual(alice_score.placement, 1.0)
        self.assertEqual(bob_score.placement, 2.0)
        self.assertEqual(charlie_score.placement, 3.0)
        self.assertEqual(diana_score.placement, 4.0)
        
        # Check calculated scores
        # Alice: (35000-30000)/1000 + 15 = 5 + 15 = 20
        # Bob: (30000-30000)/1000 + 5 = 0 + 5 = 5
        # Charlie: (25000-30000)/1000 - 5 = -5 - 5 = -10
        # Diana: (10000-30000)/1000 - 15 = -20 - 15 = -35
        alice_calc = CalculatedScore.objects.get(member=self.alice)
        bob_calc = CalculatedScore.objects.get(member=self.bob)
        charlie_calc = CalculatedScore.objects.get(member=self.charlie)
        diana_calc = CalculatedScore.objects.get(member=self.diana)
        
        self.assertAlmostEqual(alice_calc.total, 20.0, places=1)
        self.assertAlmostEqual(bob_calc.total, 5.0, places=1)
        self.assertAlmostEqual(charlie_calc.total, -10.0, places=1)
        self.assertAlmostEqual(diana_calc.total, -35.0, places=1)
    
    def test_two_way_tie_first_second(self):
        """Test tie between 1st and 2nd place."""
        score_data = [
            {'member_id': self.alice.id, 'score': 30000, 'chombo': 0},  # Tied 1st-2nd
            {'member_id': self.bob.id, 'score': 30000, 'chombo': 0},    # Tied 1st-2nd
            {'member_id': self.charlie.id, 'score': 25000, 'chombo': 0}, # 3rd
            {'member_id': self.diana.id, 'score': 15000, 'chombo': 0},  # 4th
        ]
        
        submit_session_scores('session-tie-12', self.team, score_data)
        
        # Check placements - should be 1.5 for tied players
        alice_score = RawScore.objects.get(member=self.alice, session_id='session-tie-12')
        bob_score = RawScore.objects.get(member=self.bob, session_id='session-tie-12')
        charlie_score = RawScore.objects.get(member=self.charlie, session_id='session-tie-12')
        diana_score = RawScore.objects.get(member=self.diana, session_id='session-tie-12')
        
        self.assertAlmostEqual(alice_score.placement, 1.5, places=1)
        self.assertAlmostEqual(bob_score.placement, 1.5, places=1)
        self.assertEqual(charlie_score.placement, 3.0)
        self.assertEqual(diana_score.placement, 4.0)
        
        # Check calculated scores
        # Tied players: placement 1.5, Uma = (15 + 5) / 2 = 10
        # Alice: (30000-30000)/1000 + 10 = 0 + 10 = 10
        # Bob: (30000-30000)/1000 + 10 = 0 + 10 = 10
        # Charlie: (25000-30000)/1000 - 5 = -5 - 5 = -10
        # Diana: (15000-30000)/1000 - 15 = -15 - 15 = -30
        alice_calc = CalculatedScore.objects.get(member=self.alice)
        bob_calc = CalculatedScore.objects.get(member=self.bob)
        charlie_calc = CalculatedScore.objects.get(member=self.charlie)
        diana_calc = CalculatedScore.objects.get(member=self.diana)
        
        self.assertAlmostEqual(alice_calc.total, 10.0, places=1)
        self.assertAlmostEqual(bob_calc.total, 10.0, places=1)
        self.assertAlmostEqual(charlie_calc.total, -10.0, places=1)
        self.assertAlmostEqual(diana_calc.total, -30.0, places=1)
    
    def test_two_way_tie_third_fourth(self):
        """Test tie between 3rd and 4th place."""
        score_data = [
            {'member_id': self.alice.id, 'score': 35000, 'chombo': 0},  # 1st
            {'member_id': self.bob.id, 'score': 30000, 'chombo': 0},    # 2nd
            {'member_id': self.charlie.id, 'score': 20000, 'chombo': 0}, # Tied 3rd-4th
            {'member_id': self.diana.id, 'score': 20000, 'chombo': 0},  # Tied 3rd-4th
        ]
        
        submit_session_scores('session-tie-34', self.team, score_data)
        
        # Check placements - should be 3.5 for tied players
        alice_score = RawScore.objects.get(member=self.alice, session_id='session-tie-34')
        bob_score = RawScore.objects.get(member=self.bob, session_id='session-tie-34')
        charlie_score = RawScore.objects.get(member=self.charlie, session_id='session-tie-34')
        diana_score = RawScore.objects.get(member=self.diana, session_id='session-tie-34')
        
        self.assertEqual(alice_score.placement, 1.0)
        self.assertEqual(bob_score.placement, 2.0)
        self.assertAlmostEqual(charlie_score.placement, 3.5, places=1)
        self.assertAlmostEqual(diana_score.placement, 3.5, places=1)
        
        # Check calculated scores
        # Tied players: placement 3.5, Uma = (-5 + -15) / 2 = -10
        # Alice: (35000-30000)/1000 + 15 = 5 + 15 = 20
        # Bob: (30000-30000)/1000 + 5 = 0 + 5 = 5
        # Charlie: (20000-30000)/1000 - 10 = -10 - 10 = -20
        # Diana: (20000-30000)/1000 - 10 = -10 - 10 = -20
        alice_calc = CalculatedScore.objects.get(member=self.alice)
        bob_calc = CalculatedScore.objects.get(member=self.bob)
        charlie_calc = CalculatedScore.objects.get(member=self.charlie)
        diana_calc = CalculatedScore.objects.get(member=self.diana)
        
        self.assertAlmostEqual(alice_calc.total, 20.0, places=1)
        self.assertAlmostEqual(bob_calc.total, 5.0, places=1)
        self.assertAlmostEqual(charlie_calc.total, -20.0, places=1)
        self.assertAlmostEqual(diana_calc.total, -20.0, places=1)
    
    def test_three_way_tie(self):
        """Test three-way tie for 2nd-3rd-4th place."""
        score_data = [
            {'member_id': self.alice.id, 'score': 40000, 'chombo': 0},  # 1st
            {'member_id': self.bob.id, 'score': 25000, 'chombo': 0},    # Tied 2nd-3rd-4th
            {'member_id': self.charlie.id, 'score': 25000, 'chombo': 0}, # Tied 2nd-3rd-4th
            {'member_id': self.diana.id, 'score': 25000, 'chombo': 0},  # Tied 2nd-3rd-4th
        ]
        
        submit_session_scores('session-tie-234', self.team, score_data)
        
        # Check placements - should be 3.0 for tied players (avg of 2,3,4)
        alice_score = RawScore.objects.get(member=self.alice, session_id='session-tie-234')
        bob_score = RawScore.objects.get(member=self.bob, session_id='session-tie-234')
        charlie_score = RawScore.objects.get(member=self.charlie, session_id='session-tie-234')
        diana_score = RawScore.objects.get(member=self.diana, session_id='session-tie-234')
        
        self.assertEqual(alice_score.placement, 1.0)
        self.assertAlmostEqual(bob_score.placement, 3.0, places=1)
        self.assertAlmostEqual(charlie_score.placement, 3.0, places=1)
        self.assertAlmostEqual(diana_score.placement, 3.0, places=1)
        
        # Check calculated scores
        # Tied players: placement 3.0, Uma = (5 + -5 + -15) / 3 = -15/3 = -5
        # Alice: (40000-30000)/1000 + 15 = 10 + 15 = 25
        # Bob: (25000-30000)/1000 - 5 = -5 - 5 = -10
        # Charlie: (25000-30000)/1000 - 5 = -5 - 5 = -10
        # Diana: (25000-30000)/1000 - 5 = -5 - 5 = -10
        alice_calc = CalculatedScore.objects.get(member=self.alice)
        bob_calc = CalculatedScore.objects.get(member=self.bob)
        charlie_calc = CalculatedScore.objects.get(member=self.charlie)
        diana_calc = CalculatedScore.objects.get(member=self.diana)
        
        self.assertAlmostEqual(alice_calc.total, 25.0, places=1)
        self.assertAlmostEqual(bob_calc.total, -10.0, places=1)
        self.assertAlmostEqual(charlie_calc.total, -10.0, places=1)
        self.assertAlmostEqual(diana_calc.total, -10.0, places=1)
    
    def test_four_way_tie(self):
        """Test all four players tied."""
        score_data = [
            {'member_id': self.alice.id, 'score': 30000, 'chombo': 0},
            {'member_id': self.bob.id, 'score': 30000, 'chombo': 0},
            {'member_id': self.charlie.id, 'score': 30000, 'chombo': 0},
            {'member_id': self.diana.id, 'score': 30000, 'chombo': 0},
        ]
        
        submit_session_scores('session-tie-all', self.team, score_data)
        
        # Check placements - should be 2.5 for all (avg of 1,2,3,4)
        alice_score = RawScore.objects.get(member=self.alice, session_id='session-tie-all')
        bob_score = RawScore.objects.get(member=self.bob, session_id='session-tie-all')
        charlie_score = RawScore.objects.get(member=self.charlie, session_id='session-tie-all')
        diana_score = RawScore.objects.get(member=self.diana, session_id='session-tie-all')
        
        self.assertAlmostEqual(alice_score.placement, 2.5, places=1)
        self.assertAlmostEqual(bob_score.placement, 2.5, places=1)
        self.assertAlmostEqual(charlie_score.placement, 2.5, places=1)
        self.assertAlmostEqual(diana_score.placement, 2.5, places=1)
        
        # Check calculated scores
        # All tied: placement 2.5, Uma = (15 + 5 + -5 + -15) / 4 = 0
        # All: (30000-30000)/1000 + 0 = 0 + 0 = 0
        alice_calc = CalculatedScore.objects.get(member=self.alice)
        bob_calc = CalculatedScore.objects.get(member=self.bob)
        charlie_calc = CalculatedScore.objects.get(member=self.charlie)
        diana_calc = CalculatedScore.objects.get(member=self.diana)
        
        self.assertAlmostEqual(alice_calc.total, 0.0, places=1)
        self.assertAlmostEqual(bob_calc.total, 0.0, places=1)
        self.assertAlmostEqual(charlie_calc.total, 0.0, places=1)
        self.assertAlmostEqual(diana_calc.total, 0.0, places=1)
    
    def test_session_details_with_ties(self):
        """Test get_session_details returns correct Uma for tied players."""
        score_data = [
            {'member_id': self.alice.id, 'score': 30000, 'chombo': 0},  # Tied 1st-2nd
            {'member_id': self.bob.id, 'score': 30000, 'chombo': 0},    # Tied 1st-2nd
            {'member_id': self.charlie.id, 'score': 20000, 'chombo': 0}, # Tied 3rd-4th
            {'member_id': self.diana.id, 'score': 20000, 'chombo': 0},  # Tied 3rd-4th
        ]
        
        submit_session_scores('session-details-test', self.team, score_data)
        
        # Get session details
        details = get_session_details('session-details-test', self.team)
        
        self.assertIsNotNone(details)
        self.assertEqual(len(details['players']), 4)
        
        # Find players in the details
        players_by_name = {p['member']: p for p in details['players']}
        
        # Check Alice and Bob (tied 1st-2nd, placement 1.5, Uma = (15+5)/2 = 10)
        alice_details = players_by_name['Alice']
        bob_details = players_by_name['Bob']
        
        self.assertAlmostEqual(alice_details['placement'], 1.5, places=1)
        self.assertAlmostEqual(bob_details['placement'], 1.5, places=1)
        self.assertAlmostEqual(alice_details['uma'], 10.0, places=1)
        self.assertAlmostEqual(bob_details['uma'], 10.0, places=1)
        self.assertAlmostEqual(alice_details['calculated_score'], 10.0, places=1)
        self.assertAlmostEqual(bob_details['calculated_score'], 10.0, places=1)
        
        # Check Charlie and Diana (tied 3rd-4th, placement 3.5, Uma = (-5+-15)/2 = -10)
        charlie_details = players_by_name['Charlie']
        diana_details = players_by_name['Diana']
        
        self.assertAlmostEqual(charlie_details['placement'], 3.5, places=1)
        self.assertAlmostEqual(diana_details['placement'], 3.5, places=1)
        self.assertAlmostEqual(charlie_details['uma'], -10.0, places=1)
        self.assertAlmostEqual(diana_details['uma'], -10.0, places=1)
        self.assertAlmostEqual(charlie_details['calculated_score'], -20.0, places=1)
        self.assertAlmostEqual(diana_details['calculated_score'], -20.0, places=1)
    
    def test_chombo_multiplier(self):
        """Test that multiple chombos are multiplied correctly."""
        score_data = [
            {'member_id': self.alice.id, 'score': 35000, 'chombo': 0},  # 1st
            {'member_id': self.bob.id, 'score': 30000, 'chombo': 2},    # 2nd with 2 chombos
            {'member_id': self.charlie.id, 'score': 25000, 'chombo': 0}, # 3rd
            {'member_id': self.diana.id, 'score': 10000, 'chombo': 1},  # 4th with 1 chombo
        ]
        
        submit_session_scores('session-chombo', self.team, score_data)
        
        # Check calculated scores
        # Alice: (35000-30000)/1000 + 15 = 5 + 15 = 20
        # Bob: (30000-30000)/1000 + 5 - (30*2) = 0 + 5 - 60 = -55
        # Charlie: (25000-30000)/1000 - 5 = -5 - 5 = -10
        # Diana: (10000-30000)/1000 - 15 - (30*1) = -20 - 15 - 30 = -65
        alice_calc = CalculatedScore.objects.get(member=self.alice)
        bob_calc = CalculatedScore.objects.get(member=self.bob)
        charlie_calc = CalculatedScore.objects.get(member=self.charlie)
        diana_calc = CalculatedScore.objects.get(member=self.diana)
        
        self.assertAlmostEqual(alice_calc.total, 20.0, places=1)
        self.assertAlmostEqual(bob_calc.total, -55.0, places=1)
        self.assertAlmostEqual(charlie_calc.total, -10.0, places=1)
        self.assertAlmostEqual(diana_calc.total, -65.0, places=1)
        
        # Also check session details
        details = get_session_details('session-chombo', self.team)
        players_by_name = {p['member']: p for p in details['players']}
        
        bob_details = players_by_name['Bob']
        diana_details = players_by_name['Diana']
        
        self.assertEqual(bob_details['chombo'], 2)
        self.assertEqual(diana_details['chombo'], 1)
        self.assertAlmostEqual(bob_details['calculated_score'], -55.0, places=1)
        self.assertAlmostEqual(diana_details['calculated_score'], -65.0, places=1)


