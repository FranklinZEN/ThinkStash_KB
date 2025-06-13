# run_local_worker.ps1

# Get the directory where the script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Construct the path to the .env.worker file
$envFile = Join-Path $ScriptDir ".env.worker"

# Load environment variables from .env.worker if it exists
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        # Ignore comments and empty lines
        if ($_ -and $_ -notmatch '^\s*#') {
            # Split on the first '='
            $name, $value = $_.Split('=', 2)
            # Trim whitespace from name and value
            $name = $name.Trim()
            $value = $value.Trim()

            # If the value is quoted, remove the quotes. Handles both single and double quotes.
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            
            # Set the environment variable for the current process
            [System.Environment]::SetEnvironmentVariable($name, $value, 'Process')
            Write-Host "Loaded env var: $name"
        }
    }
} else {
    Write-Warning "Warning: .env.worker file not found at $envFile. The worker might fail if it requires environment variables."
}

# Construct the path to the worker.py script
$workerScript = Join-Path $ScriptDir "worker.py"

# Run the worker script directly
Write-Host "Starting the Python worker script at $workerScript..."
python $workerScript 