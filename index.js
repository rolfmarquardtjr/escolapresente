const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const fetch = require('node-fetch');
const fs = require('fs');
const path = require('path');
const qrcode = require('qrcode');
const puppeteer = require('puppeteer');

// Caminho para os arquivos de autenticação
const authPath = path.join(__dirname, '.wwebjs_auth');

// Inicializa o Express
const app = express();
app.use(express.json());

let client = null; // Cliente WhatsApp global para reinicialização
let qrGenerated = false; // Flag para verificar se o QR foi gerado
let qrCode = null; // Variável para armazenar o QR Code em base64

// Função para inicializar o cliente WhatsApp
async function initWhatsAppClient() {
    const browser = await puppeteer.launch({
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--single-process', // Evita problemas de multiplos processos
            '--disable-gpu'
        ]
    });

    client = new Client({
        authStrategy: new LocalAuth(),
        puppeteer: { browser: browser }
    });

    client.on('qr', (qr) => {
        console.log('QR Code atualizado. Use a API /get-qr para obter o QR Code.');

        // Gera o QR Code como uma imagem PNG em base64
        qrcode.toDataURL(qr, (err, url) => {
            if (err) {
                console.error('Erro ao gerar o QR Code:', err);
            } else {
                qrCode = url; // Armazena o QR Code em base64
                qrGenerated = true; // Marca que o QR Code foi gerado
                console.log('QR Code gerado com sucesso.');
            }
        });
    });

    client.on('ready', () => {
        console.log('WhatsApp está pronto!');
    });

    client.on('message', message => {
        console.log(`Mensagem recebida de ${message.from}: ${message.body}`);

        const numero = message.from.replace('@c.us', '');
        const webhookUrl = 'http://localhost:5000/webhook';  // URL do Flask

        const payload = {
            from: message.from,
            body: message.body
        };

        fetch(webhookUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (response.ok) {
                console.log("Resposta enviada para o webhook com sucesso.");
            } else {
                console.error("Erro ao enviar a resposta para o webhook:", response.statusText);
            }
        })
        .catch(err => {
            console.error("Erro ao conectar ao webhook:", err);
        });
    });

    client.on('disconnected', () => {
        console.log('Cliente WhatsApp desconectado.');
    });

    // Inicializa o cliente do WhatsApp
    await client.initialize();
}

// Função para limpar os arquivos de autenticação e resetar o WhatsApp
function limparAutenticacao() {
    return new Promise((resolve, reject) => {
        fs.rm(authPath, { recursive: true, force: true }, (err) => {
            if (err) {
                return reject(err);
            }
            console.log('Sessão do WhatsApp destruída com sucesso.');
            resolve();
        });
    });
}

// Função para destruir o cliente e reiniciar o processo do WhatsApp
async function resetWhatsAppClient() {
    if (client) {
        try {
            await client.destroy();
            await limparAutenticacao();
            console.log('Cliente WhatsApp destruído. Reinicializando para novo QR Code...');
            await initWhatsAppClient();  // Reinicializa o cliente do WhatsApp
        } catch (err) {
            console.error("Erro ao resetar o cliente WhatsApp:", err);
            throw err;
        }
    } else {
        throw new Error('Cliente WhatsApp não está inicializado.');
    }
}

// Rota para resetar o cliente WhatsApp
app.post('/reset-whatsapp', async (req, res) => {
    try {
        await resetWhatsAppClient();
        res.json({ status: 'WhatsApp reinicializado com sucesso' });
    } catch (err) {
        res.status(500).json({ status: 'Erro ao resetar o WhatsApp', error: err.message });
    }
});

// Endpoint para obter o QR Code atualizado
app.get('/get-qr', (req, res) => {
    if (qrCode) {
        res.json({ qr: qrCode });  // qrCode contém o base64 da imagem PNG
    } else {
        res.status(404).json({ error: 'QR Code não encontrado.' });
    }
});

// Rota para enviar mensagem via API POST
app.post('/send', async (req, res) => {
    const { numero, mensagem } = req.body;
    const chatId = `${numero}@c.us`;  // Concatena o sufixo correto

    try {
        const response = await client.sendMessage(chatId, mensagem);
        res.json({ status: 'Mensagem enviada', response });
    } catch (err) {
        console.error("Erro ao enviar mensagem:", err);
        res.status(500).json({ status: 'Erro ao enviar mensagem', error: err.message });
    }
});

// Inicializa o cliente do WhatsApp na primeira execução
(async () => {
    try {
        await initWhatsAppClient();
        // Inicia o servidor Express na porta 3000
        app.listen(3000, () => {
            console.log('API rodando na porta 3000');
        });
    } catch (err) {
        console.error("Erro ao inicializar o cliente WhatsApp:", err);
    }
})();
