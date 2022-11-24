# Malicious macros should be blocked
# see https://github.com/clr2of8/VBAstomp and https://github.com/decalage2/oletools/wiki/mraptor
python3 tests/email_test.py message-macro-stomp "tests/compose/filters/2003x32_word_msgbox_stomped_fakecode.doc"
if [ $? -eq 25 ]; then
	exit 0
else
	exit 1
fi
python3 tests/email_test.py message-autoexec-macro "tests/compose/filters/excel4_sample_macro.slk"
if [ $? -eq 25 ]; then
	exit 0
else
	exit 1
fi
