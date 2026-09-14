"use strict";
const {onRequest} = require("firebase-functions/v2/https");
const {initializeApp} = require("firebase-admin/app");
const {getFirestore} = require("firebase-admin/firestore");
const {SOURCE, collect, publicStatus, mergeResult} = require("./source");
initializeApp();
// No other collections or documents are read or written by this service.
const cacheRef = getFirestore().doc("_erica_public_menu/cache");
const INTERVAL_MS = 15 * 60 * 1000;
let memory;
let loadedAt = 0;

exports.ericaMenuRelay = onRequest({
  region: "asia-northeast3", memory: "256MiB", cpu: "gcf_gen1",
  minInstances: 0, maxInstances: 1, concurrency: 1, timeoutSeconds: 40,
  invoker: "public", cors: ["https://erakeun.github.io"],
}, async (req, res) => {
  res.set("Cache-Control", "public, max-age=60");
  if (req.method !== "GET" || Object.keys(req.query).length || !["/", "/status"].includes(req.path)) {
    res.status(400).json({error: "Only fixed-source GET / or /status without query is supported"});
    return;
  }
  try {
    const now = Date.now();
    if (!memory || now - loadedAt > 60000) {
      memory = (await cacheRef.get()).data() || {};
      loadedAt = now;
    }
    // Visitors inspect status only. This path can never trigger a school request.
    if (req.path === "/status") {
      res.json(publicStatus(memory));
      return;
    }
    if (!memory.checked_at || now - Date.parse(memory.checked_at) >= INTERVAL_MS) {
      // Persist an attempt lease BEFORE the request, also across cold starts.
      const lease = await cacheRef.firestore.runTransaction(async tx => {
        const previous = (await tx.get(cacheRef)).data() || {};
        if (previous.checked_at && now - Date.parse(previous.checked_at) < INTERVAL_MS) {
          return {acquired: false, data: previous};
        }
        const data = {...previous, state: "refreshing", checked_at: new Date(now).toISOString()};
        tx.set(cacheRef, data);
        return {acquired: true, data};
      });
      memory = lease.data;
      if (lease.acquired) {
        const result = await collect(fetch);
        memory = mergeResult(memory, result);
        // A failed attempt updates status but never deletes last_good.
        await cacheRef.set(memory);
      }
      loadedAt = Date.now();
    }
    const status = publicStatus(memory);
    res.status(status.ok ? 200 : 503).json({
      ...status, source_url: SOURCE, diagnostics: memory.diagnostics || null,
      ...(status.ok ? memory.last_good : {}),
    });
  } catch (error) {
    // Infrastructure/programming errors are distinct from expected source errors.
    console.error("relay_internal_error", error);
    res.status(500).json({ok: false, state: "relay_internal_error"});
  }
});
