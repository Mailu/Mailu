python3 tests/email_test.py message-virus "tests/compose/filters/eicar.com.txt"
if [ $? -eq 99 ]; then
	exit 0
else
	exit 1
fi
