import asyncio
import os
import sys
from playwright.async_api import async_playwright
from pathlib import Path

# Directorio de datos de usuario para mantener sesión persistente y evitar baneos
USER_DATA_DIR = Path(__file__).resolve().parent / "chrome_profile"

async def login():
    print("🚀 Iniciando Chromium en modo interacción para LOGIN en el servidor...")
    print(f"Directorio de sesión: {USER_DATA_DIR}")
    
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as p:
        # Usamos launch_persistent_context
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=True, # Forzamos headless porque no hay X11
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print("🔗 Accediendo a LinkedIn...")
        await page.goto("https://www.linkedin.com/login", wait_until="networkidle")
        
        # Check if already logged in
        if "feed" in page.url:
            print("✅ Ya has iniciado sesión anteriormente.")
            await context.close()
            return

        print("\n--- FORMULARIO DE LOGIN ---")
        email = input("Introduce tu Email de LinkedIn: ")
        password = input("Introduce tu Contraseña: ")
        
        await page.fill("#username", email)
        await page.fill("#password", password)
        await page.click("button[type='submit']")
        
        await page.wait_for_timeout(5000)
        
        # Check for 2FA or verification
        if "checkpoint" in page.url or "challenge" in page.url:
            print("\n⚠️ SE REQUIERE VERIFICACIÓN (2FA o Email).")
            print(f"URL: {page.url}")
            code = input("Introduce el código de verificación enviado a tu email/app: ")
            
            # El selector del código puede variar, intentamos los más comunes
            code_input = await page.query_selector('input[name="pin"], input#input-code')
            if code_input:
                await code_input.fill(code)
                await page.click("#email-pin-submit-button, button[type='submit']")
                await page.wait_for_timeout(5000)
            else:
                print("No se encontró el campo del código. Por favor revisa manualmente.")
        
        if "feed" in page.url:
            print("\n✅ LOGIN EXITOSO! Sesión guardada en chrome_profile.")
        else:
            print(f"\n❌ Error: Login fallido. URL actual: {page.url}")
        
        await context.close()

if __name__ == "__main__":
    asyncio.run(login())
