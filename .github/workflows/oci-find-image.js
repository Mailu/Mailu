const { exec } = require("child_process");

const cmd = 'oci  compute image list --compartment-id ocid1.tenancy.oc1..aaaaaaaax2n5snd6z7n3ddnnii5x2727bh4zhjzcb7umshzorp4qnp7a2jda --operating-system "Canonical Ubuntu" --operating-system-version "22.04" --all'

const findArm = process.argv[process.argv.length-1]

if (findArm.match('arm') || findArm.match('aarch')) {
  function filter(i) {
	return !!i["display-name"].match('aarch64')
  } 
} else {
  function filter(i) {
	return !i["display-name"].match('aarch64')
  } 
}

exec(cmd, (error, stdout, stderr) => {
    if (error) {
        console.error(`error: ${error.message}`);
	process.exit(1);
        return;
    }
    if (stderr) {
        console.log(`stderr: ${stderr}`);
        return;
    }
    const result = JSON.parse(stdout);
    process.stdout.write(result.data.filter(filter)[0].id)
});
