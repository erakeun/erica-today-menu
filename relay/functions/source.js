"use strict";
const SOURCE = "https://life.hanyang.ac.kr/theme/pages/home.php";
const MENU_IDS = new Set([1, 2, 3, 4]);
const FACILITY_IDS = new Set([1, 2, 3, 4, 12, 13, 14, 15, 16, 17, 18]);
const pick = (item, keys) => Object.fromEntries(keys.filter(key => key in item).map(key => [key, item[key]]));
const kstDay = now => new Date(now.getTime() + 9 * 3600000).toISOString().slice(0, 10);

function parse(source, now) {
  const extract = name => {
    const match = source.match(new RegExp("\\bconst\\s+" + name + "\\s*=\\s*(\\[.*?\\])\\s*;", "s"));
    if (!match) throw new Error("Missing " + name);
    const data = JSON.parse(match[1]);
    if (!Array.isArray(data) || data.some(item => !item || typeof item !== "object" || Array.isArray(item))) {
      throw new Error("Invalid " + name);
    }
    return data;
  };
  const rawMenus = extract("dbMenus");
  const rawFacilities = extract("dbFacilitiesList");
  const menus = rawMenus.filter(m => MENU_IDS.has(m.facility_id)).map(m => pick(m,
    ["id", "facility_id", "meal_type", "name", "description", "price", "image_url", "target_date", "facility_name"]));
  const facilities = rawFacilities.filter(f => FACILITY_IDS.has(f.id)).map(f => pick(f,
    ["id", "name", "category", "location", "image_url"]));
  if (!rawMenus.length && [1, 2, 3, 4].every(id => facilities.some(f => f.id === id))) {
    return {ok: false, state: "not_registered"};
  }
  if (!menus.length) throw new Error("No known restaurant menu records");
  if (!menus.some(m => /^\d{4}-\d{2}-\d{2}$/.test(m.target_date || ""))) throw new Error("Missing menu dates");
  const today = kstDay(now);
  if (!menus.some(m => m.target_date === today)) return {ok: false, state: "stale_source"};
  if (!menus.some(m => m.target_date === today && typeof m.name === "string" && m.name.trim() && ["breakfast", "lunch", "dinner"].includes(m.meal_type))) {
    throw new Error("No valid menu items");
  }
  return {ok: true, state: "ready", data: {menus, facilities}};
}

async function collect(fetcher, now = new Date()) {
  const checked_at = now.toISOString();
  let response;
  let source;
  try {
    response = await fetcher(SOURCE, {
      headers: {"User-Agent": "ERICA-Today-Menu/1.0 (+https://github.com/erakeun/erica-today-menu)", "Accept": "text/html", "Accept-Language": "ko-KR,ko;q=0.9"},
      // Never follow a redirect to an arbitrary new target.
      redirect: "manual", signal: AbortSignal.timeout(20000),
    });
    source = await response.text();
  } catch (error) {
    console.warn(JSON.stringify({event: "source_exception", exception: error.name, message: error.message}));
    return {ok: false, state: "source_error", checked_at, diagnostics: {exception: error.name}};
  }
  const diagnostics = {status: response.status, initial_url: SOURCE, final_url: response.url, bytes: Buffer.byteLength(source), content_type: response.headers.get("content-type"), redirect_location: response.headers.get("location")};
  console.info(JSON.stringify({event: "source_response", ...diagnostics}));
  if (!response.ok) return {ok: false, state: "source_error", checked_at, diagnostics};
  try {
    if (!diagnostics.content_type?.toLowerCase().includes("text/html")) throw new Error("Unexpected Content-Type");
    const result = parse(source, now);
    console.info(JSON.stringify({event: "source_parse", state: result.state, menus: result.data?.menus.length || 0, facilities: result.data?.facilities.length || 0}));
    return {...result, checked_at, diagnostics};
  } catch (error) {
    console.warn(JSON.stringify({event: "source_schema_error", exception: error.name, message: error.message}));
    return {ok: false, state: "schema_error", checked_at, diagnostics};
  }
}

function publicStatus(data) {
  return {ok: data.state === "ready" && Boolean(data.last_good?.menus?.length), state: data.state || "not_checked", checked_at: data.checked_at || null,
    last_success_at: data.last_success_at || null, menu_date: data.last_good?.menus?.find(m => m.target_date)?.target_date || null};
}
function mergeResult(previous, result) {
  const next = {...previous, ...result};
  if (result.ok) {
    next.last_good = result.data;
    next.last_success_at = result.checked_at;
  }
  delete next.data;
  return next;
}
module.exports = {SOURCE, parse, collect, publicStatus, kstDay, mergeResult};
