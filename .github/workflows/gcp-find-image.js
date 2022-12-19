const { exec } = require("child_process");

const cmd =
  'gcloud --format=json compute images list --project cos-cloud --filter="family~ubuntu-minimal-2204"';

const findArm = process.argv[process.argv.length - 1];

if (findArm.match("arm") || findArm.match("aarch")) {
  function filter(i) {
    return !!i["architecture"].match("ARM64");
  }
} else {
  function filter(i) {
    return !i["architecture"].match("ARM64");
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
  process.stdout.write(result.filter(filter)[0].selfLink);
});
