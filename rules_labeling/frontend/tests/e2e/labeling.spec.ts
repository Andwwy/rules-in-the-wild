import { expect, test } from '@playwright/test';

test('labels one extraction and one classification through the UI', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByLabel('Rule text').first()).toHaveValue('The agent must inspect files before editing.');
  const extractionSave = page.waitForResponse((response) =>
    response.url().includes('/api/extraction-labels/') && response.request().method() === 'PUT',
  );
  await page.getByRole('button', { name: 'Correct' }).click();
  await expect((await extractionSave).status()).toBe(200);

  await page.getByRole('button', { name: /classification/i }).click();
  await expect(page.getByLabel('Prerequisites')).toHaveValue('before editing');
  await page.getByLabel('Triggers').fill('file edit\ncode change');
  await page.getByLabel('Ambiguity level').selectOption('none');
  await page.getByLabel('Label notes').fill('classification e2e');
  const classificationSave = page.waitForResponse((response) =>
    response.url().includes('/api/classification-labels/') && response.request().method() === 'PUT',
  );
  await page.getByRole('button', { name: 'Correct' }).click();
  await expect((await classificationSave).status()).toBe(200);
});
