import math
def calc(a,b,op):
    if op=="add": return a+b
    if op=="sub": return a-b
    if op=="mul": return a*b
    return None
class Stats:
    def mean(self, nums: list) -> float:
        return sum(nums)/len(nums)
    def stdev(self, nums: list) -> float:
        m=self.mean(nums); return math.sqrt(sum((x-m)**2 for x in nums)/len(nums))
def greet(name: str) -> str:
    """Return a greeting for the given name."""
    return "hi "+name
