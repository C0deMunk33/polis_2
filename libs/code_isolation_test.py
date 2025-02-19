import os
import tempfile
import shutil
try:
    from .code_isolation import SafeCodeExecutor, CodeExecutionResult
    from .agent import Agent
    from .common import ToolCall
except ImportError:
    from code_isolation import SafeCodeExecutor, CodeExecutionResult
    from agent import Agent
    from common import ToolCall
def test_basic_execution():
    """Test basic code execution with simple arithmetic"""
    print("\n=== Testing Basic Execution ===")
    result = executor.execute("print(2 + 2)", "Basic arithmetic test")
    print(f"Success: {result.success}")
    print(f"Output: {result.stdout}")
    assert result.success and "4" in result.stdout

def test_allowed_imports():
    """Test importing and using allowed modules"""
    print("\n=== Testing Allowed Imports ===")
    code = """
import numpy as np
arr = np.array([1, 2, 3, 4, 5])
print(f'Mean: {np.mean(arr)}')
"""
    result = executor.execute(code, "Testing numpy import and usage")
    print(f"Success: {result.success}")
    print(f"Output: {result.stdout}")
    assert result.success and "Mean: 3.0" in result.stdout

def test_file_operations():
    """Test file operations within allowed directory"""
    print("\n=== Testing File Operations ===")
    code = """
with open('test.txt', 'w') as f:
    f.write('Hello, World!')
with open('test.txt', 'r') as f:
    print(f.read())
"""
    result = executor.execute(code, "Testing file operations")
    print(f"Success: {result.success}")
    print(f"Output: {result.stdout}")
    assert result.success and "Hello, World!" in result.stdout

def test_restricted_operations():
    """Test that restricted operations are properly blocked"""
    print("\n=== Testing Restricted Operations ===")
    
    # Test attempting to import unauthorized module
    code = "import socket"
    result = executor.execute(code, "Attempting unauthorized import")
    print(f"Expected failure - unauthorized import: {not result.success}")
    
    # Test attempting to use eval
    code = "eval('2 + 2')"
    result = executor.execute(code, "Attempting to use eval")
    print(f"Expected failure - eval usage: {not result.success}")

def test_file_management():
    """Test file management functions"""
    print("\n=== Testing File Management ===")
    
    # Test saving and retrieving a file
    executor.save_code_to_environment("test_script.py", "print('Hello from test script')", "Test file management")
    
    # print contents of allowed_directory
    print(f"Contents of allowed directory: {os.listdir(executor.allowed_directory)}")

    # Test pinning a file
    result = executor.pin_file("test_script.py")
    print(f"Pin file result: {result}")
    
    # Test getting pinned files
    pinned_files = executor.get_pinned_files()
    print(f"Pinned files: {pinned_files}")
    
    # Test unpinning a file
    result = executor.unpin_file("test_script.py")
    print(f"Unpin file result: {result}")

def test_allowed_modules():
    """Test various allowed modules and their ability to write files"""
    print("\n=== Testing Allowed Modules ===")
    code = """
import numpy as np
import pandas as pd

# create a random numpy array
arr = np.random.rand(10, 10)

# save the array to a file
np.save('test_array.npy', arr)

# create a random pandas dataframe
df = pd.DataFrame({'A': np.random.rand(10), 'B': np.random.rand(10)})

# save the dataframe to a file
df.to_csv('test_dataframe.csv', index=False)


"""
    

    result = executor.execute(code, "Testing allowed modules")
    print(f"Success: {result.success}")
    print(f"Output: {result.stdout}")
    print(f"Error: {result.stderr}")
    assert result.success

    # ensure that the files were created
    assert os.path.exists('test_array.npy')
    assert os.path.exists('test_dataframe.csv')

def test_agent_tool_callback():
    """Test the agent tool callback"""
    print("\n=== Testing Agent Tool Callback ===")
    code = """
import numpy as np
import pandas as pd
# create a random numpy array
arr = np.random.rand(10, 10)

# save the array to a file
np.save('test_array.npy', arr) 

# create a random pandas dataframe
df = pd.DataFrame({'A': np.random.rand(10), 'B': np.random.rand(10)})

# save the dataframe to a file
df.to_csv('test_dataframe.csv', index=False)
"""

    tool_call = ToolCall(
        toolset_id="code_runner",
        name="execute",
        arguments={
            "code": code,
            "code_intent": "test_code_intent"
        }
    )
    
    agent = Agent(name="test_agent", private_key="test_private_key", persona="test_persona", initial_instructions="test_instructions", initial_notes=[], buffer_size=20, running=True)
    result = executor.agent_tool_callback(agent, tool_call)    
    code_execution_result = CodeExecutionResult.model_validate_json(result)
    assert code_execution_result.success
    
    
def main():
    global executor, temp_dir
    
    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    print(f"Created temporary test directory: {temp_dir}")
    
    try:
        # Initialize the executor with the temporary directory
        executor = SafeCodeExecutor(temp_dir, debug=True)
        
        # Run all tests
        test_basic_execution()
        test_allowed_imports()
        test_file_operations()
        test_restricted_operations()
        test_file_management()
        test_allowed_modules()
        test_agent_tool_callback()
        
        print("\n=== All tests completed successfully ===")
        
    except AssertionError as e:
        print(f"\nTest failed: {str(e)}")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        # stack trace
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        try:
            executor.cleanup()
            print(f"\nCleaned up temporary directory: {temp_dir}")
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    main()