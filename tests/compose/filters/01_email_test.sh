python3 tests/email_test.py message-virus "tests/compose/filters/eicar.com.txt"
if [ $? -eq 99 ]; then
    python3 tests/email_test.py message-PUA "tests/compose/filters/PotentiallyUnwanted.exe_"
    if [ $? -eq 99 ]; then
        return 0
    else
        exit 1
    fi
else
	exit 1
fi
