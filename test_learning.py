import unittest

from memory.learning import Learning


class LearningKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.data = {}
        self.store = Learning.__new__(Learning)
        self.store._read = lambda: self.data
        self.store._write = lambda data: self.data.update(data)

    def test_remembers_exact_question(self):
        self.assertTrue(self.store.learn_knowledge("¿Qué es Python?", "Un lenguaje."))
        learned = self.store.find_knowledge("¿Qué es Python?")
        self.assertEqual(learned["answer"], "Un lenguaje.")
        self.assertEqual(learned["uses"], 1)

    def test_rejects_empty_knowledge(self):
        self.assertFalse(self.store.learn_knowledge("", "Una respuesta"))
        self.assertFalse(self.store.learn_knowledge("Pregunta", ""))


if __name__ == "__main__":
    unittest.main()
