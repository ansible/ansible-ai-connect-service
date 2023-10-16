from test_utils import WisdomServiceLogAwareTestCase
from users.signals import _obfuscate


class TestSignals(WisdomServiceLogAwareTestCase):
    def test_obfuscate(self):
        self.assertEqual("*", _obfuscate("x"))
        self.assertEqual("**", _obfuscate("sh"))
        self.assertEqual("***", _obfuscate("spy"))
        self.assertEqual("h**e", _obfuscate("hide"))
        self.assertEqual("h****n", _obfuscate("hidden"))
        self.assertEqual("to******et", _obfuscate("top-secret"))
        self.assertEqual("a-lo***************alue", _obfuscate("a-long-top-secret-value"))
