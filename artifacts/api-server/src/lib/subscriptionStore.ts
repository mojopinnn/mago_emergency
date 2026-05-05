import type { PushSubscription } from "./push.js";

interface UserSubscription {
  userId: number;
  subscription: PushSubscription;
  updatedAt: number;
}

const store = new Map<number, UserSubscription>();

export function saveSubscription(userId: number, subscription: PushSubscription): void {
  store.set(userId, { userId, subscription, updatedAt: Date.now() });
}

export function getSubscription(userId: number): PushSubscription | null {
  return store.get(userId)?.subscription ?? null;
}

export function removeSubscription(userId: number): void {
  store.delete(userId);
}

export function getAllSubscriptions(): UserSubscription[] {
  return Array.from(store.values());
}
