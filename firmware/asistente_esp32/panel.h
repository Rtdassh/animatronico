// HTML del panel web servido por el ESP32 para diagnóstico directo desde Smartphone/Tablet/PC
const char PANEL_HTML[] PROGMEM = R"HTML(
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Asistente Robótico · Panel de Diagnóstico</title>
  <style>
    :root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#18243b;background:#edf2f8}
    *{box-sizing:border-box}body{margin:0}.wrap{max-width:850px;margin:auto;padding:18px}
    h1{margin:8px 0 3px;font-size:27px}h2{font-size:18px;margin:0 0 12px}
    .sub{color:#5a6b80;margin:0 0 18px}.card{background:white;border:1px solid #d5dfeb;border-radius:15px;padding:16px;margin:12px 0;box-shadow:0 3px 12px #1e3a5f0b}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
    .metric{border:1px solid #e4ebf2;border-radius:11px;padding:12px}
    .metric b{display:block;font-size:24px;margin-top:4px}.pill{display:inline-block;border-radius:999px;padding:5px 11px;font-size:13px;font-weight:700}
    .ok{color:#065f46;background:#d1fae5}.bad{color:#991b1b;background:#fee2e2}.wait{color:#854d0e;background:#fef3c7}
    button{border:0;border-radius:10px;background:#2463cf;color:white;font-size:16px;font-weight:650;padding:11px 14px;min-height:45px;cursor:pointer}
    button.alt{background:#334155}button.warn{background:#b45309}button:disabled{opacity:.5}
    .row{display:flex;flex-wrap:wrap;align-items:center;gap:9px;margin:12px 0}
    input[type=range]{width:100%;accent-color:#2463cf}.small{font-size:14px;color:#5a6b80}
    ul{padding-left:21px;margin:6px 0}li{margin:7px 0}.danger{color:#9a3412}
    #notice{font-weight:650;min-height:1.4em}.footer{padding-bottom:18px}
  </style>
</head>
<body><div class="wrap">
  <h1>Asistente de Escritorio</h1>
  <p class="sub">Panel Local · ESP32 DevKit V1 + Arduino Uno R3</p>
  <div class="card">
    <h2>Estado de la Conexión</h2>
    <div class="row"><span>Punto de Acceso Wi-Fi (ESP32)</span><span class="pill ok">ACTIVO</span></div>
    <div class="row"><span>Datos desde Arduino Uno</span><span id="uart" class="pill wait">ESPERANDO</span></div>
    <p id="age" class="small">Esperando la primera trama...</p>
    <p id="notice"></p>
  </div>
  <div class="grid">
    <div class="card"><h2>LM75A · Temperatura</h2><span id="lm" class="pill wait">ESPERANDO</span><div class="metric"><b id="temp">-- °C</b></div><p class="small" id="lmaddr"></p></div>
    <div class="card"><h2>DHT11 · Humedad</h2><span id="dht" class="pill wait">ESPERANDO</span><div class="metric"><b id="hum">-- %</b></div><p class="small" id="dhterr"></p></div>
    <div class="card"><h2>LCD 1602 · Pantalla</h2><span id="lcd" class="pill wait">ESPERANDO</span><p class="small" id="lcdaddr"></p></div>
    <div class="card"><h2>PCA9685 · Servos</h2><span id="pca" class="pill wait">ESPERANDO</span><p class="small" id="pcaaddr"></p></div>
  </div>
  <div class="card">
    <h2>Probar Componentes y Actuadores</h2>
    <div class="row"><button onclick="cmd('PING')">Probar comunicación</button><button class="alt" onclick="cmd('SCAN')">Buscar módulos I²C</button><button class="warn" onclick="cmd('BEEP')">Probar buzzer</button></div>
    <p class="small">Los botones envían la posición PWM al PCA9685. Verifique visualmente el movimiento mecánico.</p>
    <div class="row"><button onclick="cmd('S0:45')">Servo 1 · 45°</button><button onclick="cmd('S0:90')">Servo 1 · 90° (Centro)</button><button onclick="cmd('S0:135')">Servo 1 · 135°</button></div>
    <div class="row"><button onclick="cmd('S1:45')">Servo 2 · 45°</button><button onclick="cmd('S1:90')">Servo 2 · 90° (Centro)</button><button onclick="cmd('S1:135')">Servo 2 · 135°</button></div>
    <div class="row"><button class="alt" onclick="cmd('AUTO:1')">Activar alerta automática</button><button class="alt" onclick="cmd('AUTO:0')">Desactivar alerta</button></div>
    <p class="small">Alerta automática: si LM75 marca >= 30 °C o DHT11 marca >= 75 % HR, suena el buzzer y mueve el servo 1 (máx. cada 15s).</p>
    <p id="act" class="small">Último comando: ninguno</p>
  </div>
  <div class="card">
    <h2>Diagnóstico de Hardware</h2>
    <ul id="warnings"><li>Esperando telemetría inicial...</li></ul>
  </div>
</div>
<script>
const $=id=>document.getElementById(id);
const badge=(id,ok,badTxt)=>{
  const el=$(id);
  if(!el)return;
  el.className='pill '+(ok?'ok':'bad');
  el.textContent=ok?'OK':badTxt;
};
const formatT=v=>v<=-3000?'—':(v/10).toFixed(1)+' °C';
const formatH=v=>v<0?'—':(v/10).toFixed(1)+' %';
const add=(el,txt)=>{const li=document.createElement('li');li.textContent=txt;el.appendChild(li);};
async function cmd(c){
  $('act').textContent='Enviando comando: '+c+'...';
  try{
    const r=await fetch('/api/cmd?c='+encodeURIComponent(c));
    const j=await r.json();
    $('act').textContent='Comando: '+c+' -> '+(j.ok?'Enviado ('+(j.ack||'ACK')+')':'Error: '+(j.error||'desconocido'));
  }catch(e){
    $('act').textContent='Error al enviar comando: '+e;
  }
}
async function refresh(){
  try{
    const r=await fetch('/api/status');
    const d=await r.json();
    const w=$('warnings');w.innerHTML='';
    if(!d.connected){
      $('uart').className='pill bad';$('uart').textContent='SIN DATOS';
      $('age').textContent='Última trama UART: nunca';
      add(w,'Arduino Uno no está enviando datos al ESP32.');
      add(w,'Verifique: GND común, D3 -> Divisor 1k/2k -> RX2 (GPIO 16), TX2 (GPIO 17) -> D2.');
      return;
    }
    const sec=Math.round((Date.now()-d.lastFrame)/1000);
    if(sec>4){
      $('uart').className='pill bad';$('uart').textContent='TRAMA DETENIDA';
      $('age').textContent='Última trama recibida hace '+sec+' s';
      add(w,'Se interrumpió la recepción de telemetría desde Arduino.');
    }else{
      $('uart').className='pill ok';$('uart').textContent='CONECTADO ('+sec+'s)';
      $('age').textContent='Uptime Arduino: '+d.uptime+' s | ACK: '+(d.ack||'—');
    }
    badge('lm',d.lm,'NO DETECTADO');badge('dht',d.dht,'LECTURA FALLÓ');
    badge('lcd',d.lcd,'NO DETECTADA');badge('pca',d.pca,'NO DETECTADO');
    $('temp').textContent=formatT(d.temp10);$('hum').textContent=formatH(d.hum10);
    $('lmaddr').textContent='Dirección I²C: '+(d.lmAddr?'0x'+d.lmAddr.toString(16):'—');
    $('lcdaddr').textContent='Dirección I²C: '+(d.lcdAddr?'0x'+d.lcdAddr.toString(16):'—');
    $('pcaaddr').textContent='Dirección I²C: '+(d.pcaAddr?'0x'+d.pcaAddr.toString(16):'—');
    $('dhterr').textContent='Lecturas DHT11 fallidas: '+d.dhtErrors;
    if(!d.lm)add(w,'LM75A: Verifique alimentación 5V, GND, SDA a A4, SCL a A5 y dirección (0x48-0x4F).');
    if(!d.dht)add(w,'DHT11: Verifique DATA en D4, 5V, GND y resistencia pull-up (10k si no es módulo de 3 pines).');
    if(!d.lcd)add(w,'LCD 1602: No responde en 0x27 ni 0x3F. Verifique cableado I2C (A4/A5) y ajuste el contraste.');
    if(!d.pca)add(w,'PCA9685: Verifique alimentación lógica VCC (5V Arduino), GND, SDA/A4 y SCL/A5.');
    if(d.pca)add(w,'PCA9685 responde en bus I2C. Recuerde que requiere fuente de 5V externa en borne verde V+/GND para mover servos.');
    if(d.lcd)add(w,'LCD responde en bus I2C. Si la pantalla está azul sin letras, gire el potenciómetro de contraste del módulo I2C.');
    if(d.serialErrors)add(w,'Arduino reporta '+d.serialErrors+' errores en comandos serie recibidos.');
    if(d.lm&&d.dht&&d.lcd&&d.pca)add(w,'Todos los módulos de hardware reportan respuesta lógica correcta.');
    $('act').dataset.auto=d.auto?'on':'off';
  }catch(e){
    $('uart').className='pill bad';$('uart').textContent='WEB DESCONECTADA';
    $('warnings').textContent='El dispositivo móvil no puede comunicarse con el ESP32. Verifique la conexión Wi-Fi.';
  }
}
refresh();setInterval(refresh,1500);
</script></body></html>
)HTML";

