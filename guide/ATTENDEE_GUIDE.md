# Attendee guide

Follow the steps in order. Tick each box before moving on. If something fails, jump to **When something goes wrong** at the bottom.

You will need: a laptop, a Google account, a GitHub account, and a Groq account.

---

## Step 1. Get your accounts and key

- [ ] Sign up or log in at [github.com](https://github.com)
- [ ] Sign up or log in at [console.groq.com](https://console.groq.com)
- [ ] In Groq, open **API Keys**, click **Create API Key**, name it `workshop`, and copy it somewhere you can paste from. You only see it once.

Never post your key in a chat, a screenshot, or your code.

---

## Step 2. Copy the jobs Sheet

- [ ] Open the Sheet link shared in the room.
- [ ] Choose **File > Make a copy**. Keep the name or change it.
- [ ] Check that the data tab at the bottom is named exactly **Jobs**, and that row 1 holds the column names (`title` is the only required one).

You now own this copy, so you can edit anything in it.

---

## Step 3. Add the script to your Sheet

- [ ] In your copy, click **Extensions > Apps Script**.
- [ ] Delete everything in the editor.
- [ ] Open [`apps_script/Code.gs`](../apps_script/Code.gs) in this repo, click the copy icon, and paste it into the editor.
- [ ] Find this line near the top and replace the text inside the quotes with the **workshop word** shared in the room:

  ```js
  var SECRET_TOKEN = 'CHANGE_ME_TO_THE_WORKSHOP_WORD';
  ```

  Write the word down. You will need it again in Step 5.
- [ ] Click the save icon.

### Deploy it as a web app

- [ ] Click **Deploy > New deployment**.
- [ ] Click the gear icon next to *Select type* and choose **Web app**.
- [ ] Set **Execute as** to **Me**.
- [ ] Set **Who has access** to **Anyone**.
- [ ] Click **Deploy**.
- [ ] Google asks you to authorize. Click **Authorize access**, choose your account, then **Advanced > Go to (project name) (unsafe) > Allow**. This is normal for your own script.
- [ ] Copy the **Web app URL**. It ends in `/exec`.

Check it works: paste the URL into a new browser tab. You should see `Workshop web app is running.`

---

## Step 4. Create your own repo from the template

- [ ] Open the template repo page.
- [ ] Click the green **Use this template** button, then **Create a new repository**.
- [ ] Choose yourself as owner, give it a name such as `job-agent`, and click **Create repository**.

---

## Step 5. Add the three secrets

In your new repo: **Settings > Secrets and variables > Actions > New repository secret**. Add these one at a time. The names must match exactly, including capitals and underscores.

| Name | Value |
|---|---|
| `GROQ_API_KEY` | The key you copied from Groq in Step 1 |
| `APPS_SCRIPT_URL` | The web app URL from Step 3 (ends in `/exec`) |
| `SECRET_TOKEN` | The workshop word from Step 3 |

- [ ] All three secrets show in the list.

---

## Step 6. Run your agent

- [ ] Open the **Actions** tab. If GitHub asks you to enable workflows, click the green button.
- [ ] Click **Analyze jobs** on the left, then **Run workflow**, then the green **Run workflow** button.
- [ ] Refresh the page and click the new run to watch its steps.
- [ ] Wait for the green tick.

Read the log of the **Run the agent** step. You will see it fetch the jobs, count them, ask Groq, build the report, and save it.

---

## Step 7. Open your report

- [ ] Go back to your Sheet and refresh the page.
- [ ] A new menu called **AI Report** appears. Click **AI Report > Open report**.
- [ ] The first time, Google may ask you to authorize the menu. Approve it, then click the menu item again.

You should see the report with charts, insights and a takeaway. There is also a **Report** tab holding the HTML.

---

## Step 8. Make it yours

Try one change, then run the workflow again.

- Change the instructions in `SYSTEM_PROMPT` in `scripts/analyze.py` (for example, write for hiring managers instead of job seekers).
- Add skills to the `SKILLS` list.
- Change the colors in `scripts/report_template.html`.
- In the **Run workflow** box, type a different Groq model name.
- Uncomment the `schedule` lines in `.github/workflows/analyze-jobs.yml` to run the agent every week.

To edit a file on GitHub, open it and click the pencil icon, then **Commit changes**. Stuck on what to write? Paste the file into Claude or ChatGPT and describe the change you want.

---

## Check the AI's work

The counts come from Python and are exact. The sentences come from a model and can be wrong or overconfident. For each insight, find the number it cites in the charts. If you cannot find it, the sentence is not trustworthy.

---

## When something goes wrong

Open the failed run, click **Run the agent**, and read the last red line first. It usually names the problem.

| Message or symptom | What it means | What to do |
|---|---|---|
| `Missing setting GROQ_API_KEY` (or another name) | The secret is missing or misspelled | Re-add it using the exact name from Step 5 |
| `Apps Script said: Bad token` | The word in `Code.gs` and the `SECRET_TOKEN` secret differ | Make them identical. If you changed `Code.gs`, redeploy (see below) |
| `The web app did not return JSON` | Wrong URL or access is not Anyone | Redeploy with **Who has access: Anyone** and use the URL ending in `/exec` |
| `No tab named "Jobs"` | Your data tab has another name | Rename the tab to `Jobs` |
| `Groq rejected the key (401)` | Key typo, extra space, or deleted key | Create a new key and update the secret |
| `Groq does not recognise the model` | The model name is out of date | Choose a current model at console.groq.com and type it in the Run workflow box |
| `Groq returned 429` | You hit the free tier limit | The script retries on its own. If it gives up, wait a minute and run again |
| Menu says there is no report yet | The run has not finished or the Sheet is stale | Wait for the green tick and refresh the Sheet |
| No **AI Report** menu | The script has not loaded | Refresh the Sheet. Check that `onOpen` is in your pasted code |
| Report opens but charts are empty boxes | The popup could not load the chart library | Check your internet connection and open the report again |

### Redeploying after you edit Code.gs

Saving is not enough. Choose **Deploy > Manage deployments > pencil icon > Version: New version > Deploy**. The URL stays the same.

### Still stuck?

Put your hand up. Have these ready: the failed run page, and the last red line from the log. Do not share your key or your web app URL with anyone outside the room.

---

## If the wifi fails

Open [`guide/example_report.html`](example_report.html) from this repo in your browser, or download it. It is a finished example built from the sample data, so you can see what the agent produces even if your own run does not complete.
