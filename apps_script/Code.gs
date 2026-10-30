/**
 * Densight Labs - Islamabad AI Workshop
 * Google Apps Script for your COPY of the jobs Sheet.
 *
 * What this script does:
 *   1. Sends the rows of the "Jobs" tab to GitHub Actions (action: get_jobs)
 *   2. Receives the finished HTML report from GitHub Actions (action: save_report)
 *   3. Adds an "AI Report" menu that opens the report as a popup inside the Sheet
 *
 * Setup (see guide/ATTENDEE_GUIDE.md for screenshots):
 *   - Extensions > Apps Script, paste this whole file, change SECRET_TOKEN below
 *   - Deploy > New deployment > Web app
 *       Execute as: Me
 *       Who has access: Anyone
 *   - Copy the Web app URL. It becomes the APPS_SCRIPT_URL secret in your repo.
 *   - If you edit this file later, use Deploy > Manage deployments > Edit > New version.
 */

// Must be identical to the SECRET_TOKEN secret in your GitHub repo.
var SECRET_TOKEN = 'CHANGE_ME_TO_THE_WORKSHOP_WORD';

var JOBS_SHEET = 'Jobs';
var REPORT_SHEET = 'Report';

// A single Sheet cell holds at most 50,000 characters, so long HTML is split across rows.
var CHUNK_SIZE = 40000;

/** Health check: open the web app URL in a browser and you should see this text. */
function doGet() {
  return ContentService.createTextOutput('Workshop web app is running.');
}

/** GitHub Actions calls this with a JSON body: { token, action, ... } */
function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);

    if (body.token !== SECRET_TOKEN) {
      return jsonOut({ ok: false, error: 'Bad token. Check SECRET_TOKEN in Code.gs and in your repo secrets.' });
    }

    if (body.action === 'get_jobs') {
      return jsonOut({ ok: true, jobs: readJobs() });
    }

    if (body.action === 'save_report') {
      saveReport(body.html, body.meta || {});
      return jsonOut({ ok: true, saved_chars: String(body.html || '').length });
    }

    return jsonOut({ ok: false, error: 'Unknown action: ' + body.action });
  } catch (err) {
    return jsonOut({ ok: false, error: String(err) });
  }
}

/** Read the Jobs tab into a list of objects, using row 1 as the column names. */
function readJobs() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(JOBS_SHEET);
  if (!sheet) {
    throw new Error('No tab named "' + JOBS_SHEET + '". Rename your jobs tab to Jobs.');
  }
  var values = sheet.getDataRange().getDisplayValues();
  if (values.length < 2) {
    return [];
  }
  var headers = values[0].map(function (h) { return String(h).trim(); });
  var jobs = [];
  for (var r = 1; r < values.length; r++) {
    var row = {};
    var hasData = false;
    for (var c = 0; c < headers.length; c++) {
      if (headers[c]) {
        row[headers[c]] = values[r][c];
        if (values[r][c] !== '') { hasData = true; }
      }
    }
    if (hasData) { jobs.push(row); }
  }
  return jobs;
}

/** Write the HTML report into the Report tab (A1 = timestamp, A3 downward = HTML chunks). */
function saveReport(html, meta) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(REPORT_SHEET) || ss.insertSheet(REPORT_SHEET);
  sheet.clear();
  sheet.getRange('A1').setValue('Report generated: ' + new Date().toISOString());
  sheet.getRange('A2').setValue('Model: ' + (meta.model || 'unknown') + ' | Jobs analyzed: ' + (meta.jobs || '?'));

  var text = String(html || '');
  var rows = [];
  for (var i = 0; i < text.length; i += CHUNK_SIZE) {
    rows.push([text.substring(i, i + CHUNK_SIZE)]);
  }
  if (rows.length) {
    sheet.getRange(3, 1, rows.length, 1).setValues(rows);
  }
}

/** Join the stored chunks back into one HTML string. */
function readReportHtml() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(REPORT_SHEET);
  if (!sheet || sheet.getLastRow() < 3) {
    return null;
  }
  var values = sheet.getRange(3, 1, sheet.getLastRow() - 2, 1).getValues();
  return values.map(function (r) { return r[0]; }).join('');
}

/** Menu: AI Report > Open report */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('AI Report')
    .addItem('Open report', 'showReport')
    .addToUi();
}

function showReport() {
  var html = readReportHtml();
  var ui = SpreadsheetApp.getUi();
  if (!html) {
    ui.alert('No report yet. Run the workflow in GitHub Actions first, then try again.');
    return;
  }
  var output = HtmlService.createHtmlOutput(html).setWidth(1000).setHeight(700);
  ui.showModalDialog(output, 'AI job market report');
}

function jsonOut(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
