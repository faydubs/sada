/*
 * طابور التسجيلات دون اتصال — يُخزَّن في IndexedDB (الـ Blob كبير على localStorage).
 * كل عنصر: { id, file (Blob), sessionId (number|null), durationSec, createdAt }.
 */
import { openDB } from "idb";

const DB_NAME = "sada-offline";
const STORE = "pending-recordings";

function getDB() {
  return openDB(DB_NAME, 1, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
      }
    },
  });
}

export async function addPending(item) {
  const db = await getDB();
  return db.add(STORE, { ...item, createdAt: Date.now() });
}

export async function getAllPending() {
  const db = await getDB();
  return db.getAll(STORE);
}

export async function removePending(id) {
  const db = await getDB();
  return db.delete(STORE, id);
}

export async function countPending() {
  const db = await getDB();
  return db.count(STORE);
}
