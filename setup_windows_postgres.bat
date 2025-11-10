@echo off
echo Setting up PostgreSQL database for Bariatric GPT...
echo.

echo Checking PostgreSQL installation...
set "PGPATH18=C:\Program Files\PostgreSQL\18\bin"
set "PGPATH17=C:\Program Files\PostgreSQL\17\bin"
set "PGPATH16=C:\Program Files\PostgreSQL\16\bin"
set "PGPATH15=C:\Program Files\PostgreSQL\15\bin"
set "PGPATH14=C:\Program Files\PostgreSQL\14\bin"

if exist "%PGPATH18%" (
    set "PGPATH=%PGPATH18%"
    echo Found PostgreSQL 18
) else if exist "%PGPATH17%" (
    set "PGPATH=%PGPATH17%"
    echo Found PostgreSQL 17
) else if exist "%PGPATH16%" (
    set "PGPATH=%PGPATH16%"
    echo Found PostgreSQL 16
) else if exist "%PGPATH15%" (
    set "PGPATH=%PGPATH15%"
    echo Found PostgreSQL 15
) else if exist "%PGPATH14%" (
    set "PGPATH=%PGPATH14%"
    echo Found PostgreSQL 14
) else (
    echo ERROR: PostgreSQL not found in standard locations!
    echo Please check your PostgreSQL installation.
    pause
    exit /b 1
)

echo Adding PostgreSQL to PATH temporarily...
set "PATH=%PGPATH%;%PATH%"

echo.
echo Testing PostgreSQL connection...
"%PGPATH%\psql" --version

echo.
echo Running database setup script...
echo You will be prompted for the postgres user password that you set during installation.
echo.

"%PGPATH%\psql" -U postgres -f setup_windows_postgres.sql

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Database setup failed!
    echo Please check that you entered the correct postgres password.
    pause
    exit /b 1
)

echo.
echo Testing connection to new database...
set PGPASSWORD=bariatric_password
"%PGPATH%\psql" -U bariatric_user -d bariatric_db -c "SELECT 'Connection successful!' as status;"

echo.
echo Setup complete! You can now run your storage service.
pause