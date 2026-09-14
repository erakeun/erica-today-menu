/**
 * REJECTED EXPERIMENT: upstream returned HTTP 403. Not used in production.
 * Read-only Google Apps Script relay for the ERICA HY-SQUARE menu.
 *
 * Deploy as a Web app executed by the owner and accessible to anyone. This
 * accepts no target URL or request parameters and returns only the two embedded
 * data arrays needed by the site, so it cannot be used as a general-purpose
 * proxy.
 */
const HY_SQUARE_MENU_URL = 'https://life.hanyang.ac.kr/theme/pages/home.php';

function doGet() {
  const response = UrlFetchApp.fetch(HY_SQUARE_MENU_URL, {
    method: 'get',
    followRedirects: true,
    muteHttpExceptions: true,
    headers: {
      'User-Agent': 'Mozilla/5.0 (compatible; ERICA-Today-Menu/1.0)',
      'Accept-Language': 'ko-KR,ko;q=0.9',
      'Accept': 'text/html,application/xhtml+xml'
    }
  });
  const status = response.getResponseCode();
  const body = response.getContentText('UTF-8');
  if (status !== 200) return jsonOutput_({
    error: 'HY-SQUARE request failed', status: status, bytes: body.length
  });

  const menus = extractArray_(body, 'dbMenus');
  const facilities = extractArray_(body, 'dbFacilitiesList');
  return jsonOutput_({
    source_url: HY_SQUARE_MENU_URL,
    fetched_at: new Date().toISOString(),
    menus: menus,
    facilities: facilities
  });
}

function extractArray_(source, variableName) {
  const pattern = new RegExp('\\bconst\\s+' + variableName + '\\s*=\\s*(\\[[\\s\\S]*?\\])\\s*;');
  const match = source.match(pattern);
  if (!match) throw new Error(variableName + ' was not found in HY-SQUARE HTML');
  const value = JSON.parse(match[1]);
  if (!Array.isArray(value)) throw new Error(variableName + ' is not an array');
  return value;
}

function jsonOutput_(value) {
  return ContentService.createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}
