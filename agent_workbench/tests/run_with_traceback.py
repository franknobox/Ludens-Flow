import traceback
import runpy
try:
    runpy.run_path('agent_workbench/tests/test_step4_acceptance.py')
except Exception as e:
    print('\n--- ERROR TRACEBACK ---')
    traceback.print_exc()
