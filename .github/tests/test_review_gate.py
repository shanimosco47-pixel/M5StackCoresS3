"""Run the actual inline GitHub review gate against controlled GitHub API states."""
import json
from pathlib import Path
import subprocess
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]
HEAD = 'a' * 40


def summary(*, author='chatgpt-codex-connector[bot]', head=HEAD, status='completed', findings=False):
    state = {'code_review': {'commit_sha': head, 'status': status,
                             'has_any_findings': findings, 'has_unresolved_findings': findings}}
    return {'user': {'login': author}, 'body': '<!-- codex-review-state:v1 ' + json.dumps(state) + ' -->',
            'html_url': 'https://github.com/example/repo/pull/1#issuecomment-1'}


def run_gate(states):
    yaml = (ROOT / '.github/workflows/independent-review.yml').read_text(encoding='utf-8')
    script = textwrap.dedent(yaml.split('          script: |\n', 1)[1])
    runner = r'''
const fs = require('fs');
const {script, states} = JSON.parse(fs.readFileSync(0, 'utf8'));
let reads=0, posts=0, failures=[], written=false;
const github={rest:{issues:{listComments(){},async createComment(){posts++;}}},
  async paginate(){return structuredClone(states[Math.min(reads++,states.length-1)]);}};
const context={repo:{owner:'example',repo:'repo'},payload:{pull_request:{number:1,head:{sha:'a'.repeat(40)}}}};
const chain={addHeading(){return this;},addLink(){return this;},addRaw(){return this;},async write(){written=true;}};
const core={setFailed(value){failures.push(value);},summary:chain};
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
(async()=>{
  await new AsyncFunction('github','context','core','setTimeout',script)(github,context,core,fn=>fn());
  console.log(JSON.stringify({failures,written,posts}));
})().catch(error=>{console.error(error);process.exit(1);});
'''
    result = subprocess.run(['node', '-e', runner], input=json.dumps({'script': script, 'states': states}),
                            text=True, capture_output=True, check=True, timeout=10)
    return json.loads(result.stdout)


class ReviewGateTests(unittest.TestCase):
    def test_current_completed_review_passes_without_duplicate_request(self):
        result = run_gate([[summary()]])
        self.assertEqual(result['failures'], [])
        self.assertTrue(result['written'])
        self.assertEqual(result['posts'], 0)

    def test_old_commit_cannot_satisfy_gate(self):
        result = run_gate([[summary(head='b' * 40)]])
        self.assertTrue(result['failures'])
        self.assertFalse(result['written'])

    def test_untrusted_comment_author_cannot_spoof_review(self):
        result = run_gate([[summary(author='pull-request-author')]])
        self.assertTrue(result['failures'])
        self.assertFalse(result['written'])

    def test_running_review_is_awaited_and_not_restarted(self):
        result = run_gate([[summary(status='running', findings=None)], [summary()]])
        self.assertEqual(result['failures'], [])
        self.assertTrue(result['written'])
        self.assertEqual(result['posts'], 0)

    def test_missing_review_is_requested_but_never_reported_as_complete(self):
        result = run_gate([[]])
        self.assertTrue(result['failures'])
        self.assertFalse(result['written'])
        self.assertEqual(result['posts'], 1)

    def test_unresolved_findings_fail_gate(self):
        self.assertTrue(run_gate([[summary(findings=True)]])['failures'])

    def test_incomplete_state_cannot_pass(self):
        result = run_gate([[summary(findings=None)]])
        self.assertTrue(result['failures'])

    def test_malformed_bot_state_cannot_pass(self):
        comment = summary()
        comment['body'] = '<!-- codex-review-state:v1 {malformed} -->'
        self.assertTrue(run_gate([[comment]])['failures'])


if __name__ == '__main__':
    unittest.main()
