import unittest
from glmpy.basic import Gridlabd


class TestBase(unittest.TestCase):
    def test_run(self):
        glm = Gridlabd('case/system.glm')
        glm.remove_helics()
        results = glm.run()
        print(results.keys())


if __name__ == '__main__':
    unittest.main()
