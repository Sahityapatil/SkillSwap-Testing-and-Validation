from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from skills.models import SkillCategory, Skill, StudentTeachingSkill, StudentLearningInterest
from wallet.models import CreditWallet, CreditTransaction
from wallet.services import WalletService
from learning_sessions.models import LearningSession
from datetime import date, time

User = get_user_model()

class SkillSwapCoreWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create Category and Skill
        self.cat = SkillCategory.objects.create(name="Programming", slug="programming")
        self.skill_python = Skill.objects.create(
            category=self.cat,
            name="Python Programming",
            default_topics=["Variables", "Loops", "Functions", "OOP"]
        )
        self.skill_react = Skill.objects.create(
            category=self.cat,
            name="React.js",
            default_topics=["Components", "Hooks", "Props"]
        )

        # Create Student A (Tutor)
        self.tutor = User.objects.create_user(
            username="tutor_test",
            email="tutor@test.com",
            password="Password@123",
            first_name="Test",
            last_name="Tutor",
            role="student"
        )
        WalletService.create_initial_wallet(self.tutor)

        # Verified teaching skill for Tutor
        self.teaching_skill = StudentTeachingSkill.objects.create(
            student=self.tutor,
            skill=self.skill_python,
            experience_level='intermediate',
            hourly_rate=15,
            verification_status='verified',
            verification_score=90,
            is_published=True
        )

        # Create Student B (Learner)
        self.learner = User.objects.create_user(
            username="learner_test",
            email="learner@test.com",
            password="Password@123",
            first_name="Test",
            last_name="Learner",
            role="student"
        )
        WalletService.create_initial_wallet(self.learner)

    def test_registration_and_initial_credit_bonus(self):
        """Rule: New registration awards exactly 50 credits in atomic ledger."""
        reg_payload = {
            "username": "new_student",
            "email": "new@student.com",
            "password": "Password@123",
            "confirm_password": "Password@123",
            "full_name": "New Student",
            "college_name": "Test University",
            "department": "Engineering",
            "year_of_study": "1st Year",
            "learning_interests": ["Python Programming"]
        }
        res = self.client.post('/api/auth/register/', reg_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('tokens', res.data)
        self.assertEqual(res.data['user']['wallet_balance'], 50)

        # Verify database ledger record
        new_user = User.objects.get(username="new_student")
        tx = CreditTransaction.objects.filter(receiver=new_user, transaction_type='registration_bonus').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 50)
        self.assertEqual(tx.receiver_updated_balance, 50)

    def test_duplicate_username_and_email_prevention(self):
        """Rule: Reject duplicate usernames and duplicate emails."""
        duplicate_username = {
            "username": "learner_test",
            "email": "unique@student.com",
            "password": "Password@123",
            "confirm_password": "Password@123",
            "full_name": "Duplicate Test"
        }
        res1 = self.client.post('/api/auth/register/', duplicate_username, format='json')
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        duplicate_email = {
            "username": "unique_user",
            "email": "learner@test.com",
            "password": "Password@123",
            "confirm_password": "Password@123",
            "full_name": "Duplicate Test"
        }
        res2 = self.client.post('/api/auth/register/', duplicate_email, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_and_jwt_tokens(self):
        """Rule: Login succeeds with valid credentials and issues JWT access and refresh tokens."""
        res = self.client.post('/api/auth/login/', {
            "username": "learner_test",
            "password": "Password@123"
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', res.data)
        self.assertIn('access', res.data['tokens'])

    def test_session_booking_and_escrow_hold(self):
        """Rule: Booking holds session credits in escrow, deducting from available balance."""
        self.client.force_authenticate(user=self.learner)

        booking_payload = {
            "tutor_id": self.tutor.id,
            "skill_id": self.skill_python.id,
            "topics": ["Variables", "Loops"],
            "scheduled_date": str(date.today()),
            "start_time": "14:00:00",
            "duration_minutes": 60,
            "session_mode": "online"
        }
        res = self.client.post('/api/learning/sessions/request/', booking_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        session_id = res.data['id']

        # Verify learner wallet: 50 initial - 15 escrowed = 35 available, 15 escrow
        learner_wallet = CreditWallet.objects.get(user=self.learner)
        self.assertEqual(learner_wallet.available_balance, 35)
        self.assertEqual(learner_wallet.escrow_balance, 15)

        # Verify pending escrow transaction
        tx = CreditTransaction.objects.filter(session_id=session_id, transaction_type='session_escrow').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.status, 'pending')
        self.assertEqual(tx.amount, 15)

    def test_insufficient_credit_balance_rejection(self):
        """Rule: Student cannot spend more credits than available balance."""
        # Drain learner wallet
        CreditWallet.objects.filter(user=self.learner).update(available_balance=5)
        self.client.force_authenticate(user=self.learner)

        booking_payload = {
            "tutor_id": self.tutor.id,
            "skill_id": self.skill_python.id,
            "topics": ["Variables"],
            "scheduled_date": str(date.today()),
            "start_time": "15:00:00",
            "duration_minutes": 60, # requires 15 credits
            "session_mode": "online"
        }
        res = self.client.post('/api/learning/sessions/request/', booking_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient credits', res.data['error'])

    def test_mutual_session_completion_and_credit_payout(self):
        """Rule: Mutual confirmation by both teacher and learner releases payout to teacher."""
        # Create session with escrow hold
        session = LearningSession.objects.create(
            teacher=self.tutor,
            learner=self.learner,
            skill=self.skill_python,
            teaching_skill=self.teaching_skill,
            scheduled_date=date.today(),
            start_time=time(16, 0),
            duration_minutes=60,
            credit_amount=15,
            status='accepted'
        )
        WalletService.hold_session_escrow(self.learner, session.id, 15)

        # 1. Learner confirms completion
        self.client.force_authenticate(user=self.learner)
        res1 = self.client.patch(f'/api/sessions/{session.id}/complete/')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertTrue(session.learner_completed_confirmed)
        self.assertEqual(session.status, 'accepted') # Still accepted until teacher confirms

        # 2. Teacher confirms completion
        self.client.force_authenticate(user=self.tutor)
        res2 = self.client.patch(f'/api/sessions/{session.id}/complete/')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertTrue(session.is_mutually_confirmed)
        self.assertEqual(session.status, 'completed')

        # Check Wallets
        tutor_wallet = CreditWallet.objects.get(user=self.tutor)
        learner_wallet = CreditWallet.objects.get(user=self.learner)

        # Tutor: 50 initial + 15 payout = 65
        self.assertEqual(tutor_wallet.available_balance, 65)
        self.assertEqual(tutor_wallet.total_earned, 15)

        # Learner: 50 - 15 = 35 available, 0 in escrow, 15 total spent
        self.assertEqual(learner_wallet.available_balance, 35)
        self.assertEqual(learner_wallet.escrow_balance, 0)
        self.assertEqual(learner_wallet.total_spent, 15)

        # Verify immutable payout transaction
        payout_tx = CreditTransaction.objects.filter(session_id=session.id, transaction_type='session_payout').first()
        self.assertIsNotNone(payout_tx)
        self.assertEqual(payout_tx.status, 'completed')
        self.assertEqual(payout_tx.amount, 15)

    def test_session_cancellation_and_escrow_refund(self):
        """Rule: Cancelled sessions automatically refund escrowed credits to the learner."""
        session = LearningSession.objects.create(
            teacher=self.tutor,
            learner=self.learner,
            skill=self.skill_python,
            teaching_skill=self.teaching_skill,
            scheduled_date=date.today(),
            start_time=time(17, 0),
            duration_minutes=60,
            credit_amount=15,
            status='accepted'
        )
        WalletService.hold_session_escrow(self.learner, session.id, 15)

        # Learner cancels
        self.client.force_authenticate(user=self.learner)
        res = self.client.post(f'/api/sessions/{session.id}/cancel/', {"reason": "Schedule conflict"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        learner_wallet = CreditWallet.objects.get(user=self.learner)
        # Refunded: back to 50 available, 0 escrow
        self.assertEqual(learner_wallet.available_balance, 50)
        self.assertEqual(learner_wallet.escrow_balance, 0)

        # Refund transaction exists
        refund_tx = CreditTransaction.objects.filter(session_id=session.id, transaction_type='session_refund').first()
        self.assertIsNotNone(refund_tx)
        self.assertEqual(refund_tx.amount, 15)
