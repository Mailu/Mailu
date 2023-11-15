python3 tests/email_test.py message-virus "tests/compose/filters/eicar.com.txt"
if [ $? -ne 25 ]; then
  exit 1
fi
python3 tests/email_test.py message-PUA "tests/compose/filters/PotentiallyUnwanted.exe_"
if [ $? -ne 25 ]; then
  exit 1
fi

exit 0
