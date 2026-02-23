const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const fs = require('fs-extra');
const path = require('path');

const app = express();
const PORT = 3000;
const DATA_FILE = path.join(__dirname, 'data.json');
const CONFIG_FILE = path.join(__dirname, 'config.json');

let config = { GAS_WEBAPP_URL: "" };
async function loadConfig() {
    if (await fs.pathExists(CONFIG_FILE)) {
        config = await fs.readJson(CONFIG_FILE);
    }
}
loadConfig();

app.use(cors());
app.use(bodyParser.json());
app.use(express.static(__dirname));

// Utility to read data
async function readData() {
    try {
        if (!await fs.pathExists(DATA_FILE)) {
            const initialData = {
                items: [],
                brands: [],
                categories: [],
                stockMap: {},
                rentals: [],
                outfits: [],
                schedule: [],
                handlings: [],
                variationsMap: {}
            };
            await fs.writeJson(DATA_FILE, initialData, { spaces: 2 });
            return initialData;
        }
        return await fs.readJson(DATA_FILE);
    } catch (err) {
        console.error('Error reading data file:', err);
        return null;
    }
}

// Utility to write data and trigger backup
async function writeData(data) {
    try {
        await fs.writeJson(DATA_FILE, data, { spaces: 2 });
        // Background sync to GAS
        syncToGas(data);
        return true;
    } catch (err) {
        console.error('Error writing data file:', err);
        return false;
    }
}

// Automated Backup to GAS
async function syncToGas(data) {
    if (!config.GAS_WEBAPP_URL) return;
    try {
        console.log('Starting background sync to Google Sheets...');
        // We use the 'import' action or similar that you have in GAS
        // If your GAS doPost handles different actions, we need to match it.
        // Assuming we use the existing registerProductData or similar logic, 
        // but for a full backup, we might need a dedicated 'syncAll' in GAS.
        // For now, let's just send the data.
        await fetch(config.GAS_WEBAPP_URL, {
            method: 'POST',
            body: JSON.stringify({ action: "manualSync", payload: data }),
            headers: { 'Content-Type': 'application/json' }
        });
        console.log('Sync to Google Sheets successful.');
    } catch (err) {
        console.error('Sync to Google Sheets failed:', err.message);
    }
}

app.get('/api/data', async (req, res) => {
    const data = await readData();
    res.json({ success: true, ...data });
});

app.post('/api/saveInventoryData', async (req, res) => {
    const payload = req.body;
    const data = await readData();
    const now = new Date().toISOString();

    // Simplistic integration for now, similar to GAS logic
    payload.matrix.forEach(m => {
        const key = `${payload.code}_${m.color}_${m.size}`;
        data.stockMap[key] = (data.stockMap[key] || 0) + Number(m.qty);

        // Update variations if needed
        if (!data.variationsMap[payload.code]) {
            data.variationsMap[payload.code] = { colors: [], sizes: [] };
        }
        if (!data.variationsMap[payload.code].colors.includes(m.color)) {
            data.variationsMap[payload.code].colors.push(m.color);
        }
        if (!data.variationsMap[payload.code].sizes.includes(m.size)) {
            data.variationsMap[payload.code].sizes.push(m.size);
        }
    });

    await writeData(data);
    res.json({ success: true, message: "재고 등록 완료" });
});

app.post('/api/processRental', async (req, res) => {
    const payload = req.body;
    const data = await readData();
    const now = new Date().toISOString();

    payload.items.forEach(item => {
        data.rentals.push({
            code: item.code,
            name: item.name,
            color: item.color,
            size: item.size,
            qty: Number(item.qty),
            renter: payload.renter,
            date: now,
            type: payload.type || "대여",
            timestamp: Date.now(),
            returnTime: ""
        });
    });

    await writeData(data);
    res.json({ success: true, message: "대여 등록 완료" });
});

app.post('/api/processReturn', async (req, res) => {
    const payload = req.body;
    const data = await readData();
    const now = new Date().toISOString();

    payload.items.forEach(item => {
        const rental = data.rentals.find(r => r.timestamp === item.timestamp || (r.code === item.code && r.renter === item.renter && !r.returnTime));
        if (rental) {
            rental.returnTime = now;
        }
    });

    await writeData(data);
    res.json({ success: true, message: "반납 처리 완료" });
});

app.post('/api/import', async (req, res) => {
    const data = req.body;
    if (await writeData(data)) {
        res.json({ success: true, message: "데이터 마이그레이션 완료" });
    } else {
        res.status(500).json({ success: false, error: "파일 저장 실패" });
    }
});

app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});
