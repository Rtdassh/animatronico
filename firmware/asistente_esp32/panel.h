// HTML del panel web servido por el ESP32 para diagnóstico directo y control cinemático de servos
const char PANEL_HTML[] PROGMEM = R"HTML(
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Asistente Robótico · Panel de Control y Diagnóstico</title>
  <style>
    :root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#18243b;background:#edf2f8}
    *{box-sizing:border-box}body{margin:0;padding:0}.wrap{max-width:960px;margin:auto;padding:16px}
    h1{margin:6px 0 2px;font-size:26px}h2{font-size:17px;margin:0 0 10px}h3{font-size:15px;margin:0 0 8px;color:#1e3a8a}
    .sub{color:#5a6b80;margin:0 0 14px;font-size:14px}.card{background:white;border:1px solid #d5dfeb;border-radius:14px;padding:15px;margin:12px 0;box-shadow:0 3px 12px #1e3a5f0b}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}
    .grid-servos{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
    .grid-exp{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}
    .metric{border:1px solid #e4ebf2;border-radius:10px;padding:10px;margin-top:8px}
    .metric b{display:block;font-size:23px;margin-top:2px}.pill{display:inline-block;border-radius:999px;padding:4px 10px;font-size:12px;font-weight:700}
    .ok{color:#065f46;background:#d1fae5}.bad{color:#991b1b;background:#fee2e2}.wait{color:#854d0e;background:#fef3c7}
    .accent{color:#1e40af;background:#dbeafe}.neutral{color:#334155;background:#e2e8f0}
    
    /* Pestañas */
    .tabs-nav{display:flex;gap:8px;margin:12px 0 16px;border-bottom:2px solid #cbd5e1;padding-bottom:8px}
    .tab-btn{background:transparent;color:#475569;border:0;font-size:15px;font-weight:700;padding:10px 16px;border-radius:9px;cursor:pointer;transition:all .15s}
    .tab-btn:hover{background:#e2e8f0;color:#0f172a}
    .tab-btn.active{background:#2463cf;color:#ffffff;box-shadow:0 2px 8px #2463cf33}
    .tab-content{display:none}
    .tab-content.active{display:block}

    /* Botones y Controles */
    button{border:0;border-radius:9px;background:#2463cf;color:white;font-size:14px;font-weight:650;padding:9px 13px;min-height:38px;cursor:pointer;transition:background .15s}
    button:hover{background:#1d4ed8}
    button.alt{background:#334155}button.alt:hover{background:#1e293b}
    button.warn{background:#b45309}button.warn:hover{background:#92400e}
    button.subtle{background:#e2e8f0;color:#1e293b;font-weight:600}button.subtle:hover{background:#cbd5e1}
    button.sm{min-height:32px;padding:5px 9px;font-size:12px}
    .row{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:10px 0}
    .servo-box{border:1px solid #e2e8f0;border-radius:11px;padding:12px;background:#f8fafc}
    .servo-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
    .servo-title{font-weight:700;font-size:13px;color:#1e293b}
    input[type=range]{width:100%;accent-color:#2463cf;margin:8px 0;cursor:pointer}
    .slider-labels{display:flex;justify-content:space-between;font-size:11px;color:#64748b}
    .small{font-size:13px;color:#5a6b80}ul{padding-left:20px;margin:6px 0}li{margin:6px 0}
    #notice{font-weight:650;min-height:1.3em}.status-bar{background:#0f172a;color:#f8fafc;padding:10px 14px;border-radius:10px;font-size:13px;display:flex;justify-content:space-between;align-items:center;margin-top:14px}
  </style>
</head>
<body><div class="wrap">
  <h1>Asistente de Escritorio</h1>
  <p class="sub">Panel Autónomo · ESP32 DevKit V1 + Arduino Uno R3 (Gran Hermano)</p>

  <!-- NAVEGACIÓN POR PESTAÑAS -->
  <div class="tabs-nav">
    <button id="btn-tab-diag" class="tab-btn active" onclick="switchTab('diag')">📊 Diagnóstico y Sensores</button>
    <button id="btn-tab-servos" class="tab-btn" onclick="switchTab('servos')">🎮 Control de Servos (PCA9685)</button>
  </div>

  <!-- ===================================================================== -->
  <!-- PESTAÑA 1: DIAGNÓSTICO Y SENSORES (ASISTENTE COMPLETO) -->
  <!-- ===================================================================== -->
  <div id="tab-diag" class="tab-content active">
    <div class="card">
      <h2>Estado de la Conexión</h2>
      <div class="row"><span>Punto de Acceso Wi-Fi (ESP32)</span><span class="pill ok">ACTIVO (192.168.4.1)</span></div>
      <div class="row"><span>Datos desde Arduino Uno</span><span id="uart" class="pill wait">ESPERANDO</span></div>
      <p id="age" class="small">Esperando la primera trama UART...</p>
      <p id="notice"></p>
    </div>

    <div class="grid">
      <div class="card">
        <h2>LM75A · Temperatura</h2><span id="lm" class="pill wait">ESPERANDO</span>
        <div class="metric"><b id="temp">-- °C</b></div>
        <p class="small" id="lmaddr"></p>
      </div>
      <div class="card">
        <h2>DHT11 · Humedad</h2><span id="dht" class="pill wait">ESPERANDO</span>
        <div class="metric"><b id="hum">-- %</b></div>
        <p class="small" id="dhterr"></p>
      </div>
      <div class="card">
        <h2>LCD 1602 · Pantalla</h2><span id="lcd" class="pill wait">ESPERANDO</span>
        <p class="small" id="lcdaddr"></p>
      </div>
      <div class="card">
        <h2>PCA9685 · Controlador Servos</h2><span id="pca" class="pill wait">ESPERANDO</span>
        <p class="small" id="pcaaddr"></p>
      </div>
    </div>

    <div class="card">
      <h2>Pruebas Rápidas de Hardware</h2>
      <div class="row">
        <button onclick="cmd('PING')">Probar comunicación</button>
        <button class="alt" onclick="cmd('SCAN')">Buscar módulos I²C</button>
        <button class="warn" onclick="cmd('BEEP')">Probar buzzer (D8)</button>
        <button class="subtle" onclick="switchTab('servos')">Ir al control de servos ➔</button>
      </div>
      <div class="row">
        <button class="alt" onclick="cmd('AUTO:1')">Activar alerta automática</button>
        <button class="subtle" onclick="cmd('AUTO:0')">Desactivar alerta</button>
      </div>
      <p class="small">Alerta automática: si LM75A marca &ge; 30 °C o DHT11 marca &ge; 75 % HR, suena el buzzer y mueve el servo principal (máx. cada 15 s).</p>
    </div>

    <div class="card">
      <h2>Diagnóstico de Hardware y Lista de Avisos</h2>
      <ul id="warnings"><li>Esperando telemetría inicial...</li></ul>
    </div>
  </div>

  <!-- ===================================================================== -->
  <!-- PESTAÑA 2: CONTROL DE SERVOS (PCA9685 - 16 CANALES) -->
  <!-- ===================================================================== -->
  <div id="tab-servos" class="tab-content">
    <div class="card">
      <h2>Control Cinemático PCA9685 (16 Canales PWM)</h2>
      <p class="small">El chip PCA9685 provee 16 canales independientes de modulación PWM de 12 bits. Los servomotores deben recibir energía mediante el <b>borne verde de fuerza V+/GND</b> alimentado por la salida ajustada a 5.0 V del convertidor LM2596.</p>
      
      <!-- Poses rápidas globales -->
      <div class="row">
        <button onclick="cmd('S_ALL:90')">Centrar Todos a 90°</button>
        <button class="alt" onclick="cmd('S_ALL:45')">Pose Extrema (45°)</button>
        <button class="alt" onclick="cmd('S_ALL:135')">Pose Extrema (135°)</button>
        <button class="warn" onclick="cmd('BEEP')">Buzzer de Alerta</button>
      </div>
    </div>

    <!-- SECCIÓN 1: SERVOS PRINCIPALES DEL ASISTENTE (CH 0 A 5) -->
    <div class="card">
      <h2>Servomotores Principales del Asistente (Canales 0 a 5)</h2>
      <p class="small">Canales primarios destinados a la cabeza animatrónica, mecanismo de ojos y brazo robótico interactivo:</p>

      <div class="grid-servos">
        <!-- CANAL 0: SERVO 1 (BRAZO / PAN) -->
        <div class="servo-box">
          <div class="servo-head">
            <span class="servo-title">Canal 0 · Servo 1 (Brazo / Pan)</span>
            <span id="ang-0" class="pill accent">90°</span>
          </div>
          <input type="range" id="slider-0" min="30" max="150" value="90" oninput="onSlider('0',this.value)" onchange="sendServo('0',this.value)">
          <div class="slider-labels"><span>30°</span><span>90° (Centro)</span><span>150°</span></div>
          <div class="row" style="margin-top:8px">
            <button class="subtle sm" onclick="adjServo('0',-5)">◀ -5°</button>
            <button class="sm" onclick="setServo('0',45)">45°</button>
            <button class="sm" onclick="setServo('0',90)">90°</button>
            <button class="sm" onclick="setServo('0',135)">135°</button>
            <button class="subtle sm" onclick="adjServo('0',5)">+5° ▶</button>
          </div>
        </div>

        <!-- CANAL 1: SERVO 2 (CABEZA / TILT) -->
        <div class="servo-box">
          <div class="servo-head">
            <span class="servo-title">Canal 1 · Servo 2 (Cabeza / Tilt)</span>
            <span id="ang-1" class="pill accent">90°</span>
          </div>
          <input type="range" id="slider-1" min="30" max="150" value="90" oninput="onSlider('1',this.value)" onchange="sendServo('1',this.value)">
          <div class="slider-labels"><span>30°</span><span>90° (Centro)</span><span>150°</span></div>
          <div class="row" style="margin-top:8px">
            <button class="subtle sm" onclick="adjServo('1',-5)">◀ -5°</button>
            <button class="sm" onclick="setServo('1',45)">45°</button>
            <button class="sm" onclick="setServo('1',90)">90°</button>
            <button class="sm" onclick="setServo('1',135)">135°</button>
            <button class="subtle sm" onclick="adjServo('1',5)">+5° ▶</button>
          </div>
        </div>

        <!-- CANAL 2: SERVO 3 (PÁRPADO SUP. / GARRA / ANTENA 1) -->
        <div class="servo-box">
          <div class="servo-head">
            <span class="servo-title">Canal 2 · Servo 3 (Párpado / Aux 1)</span>
            <span id="ang-2" class="pill neutral">90°</span>
          </div>
          <input type="range" id="slider-2" min="30" max="150" value="90" oninput="onSlider('2',this.value)" onchange="sendServo('2',this.value)">
          <div class="slider-labels"><span>30°</span><span>90°</span><span>150°</span></div>
          <div class="row" style="margin-top:8px">
            <button class="subtle sm" onclick="adjServo('2',-5)">◀ -5°</button>
            <button class="sm" onclick="setServo('2',45)">45°</button>
            <button class="sm" onclick="setServo('2',90)">90°</button>
            <button class="sm" onclick="setServo('2',135)">135°</button>
            <button class="subtle sm" onclick="adjServo('2',5)">+5° ▶</button>
          </div>
        </div>

        <!-- CANAL 3: SERVO 4 (PÁRPADO INF. / BASE / ANTENA 2) -->
        <div class="servo-box">
          <div class="servo-head">
            <span class="servo-title">Canal 3 · Servo 4 (Párpado / Aux 2)</span>
            <span id="ang-3" class="pill neutral">90°</span>
          </div>
          <input type="range" id="slider-3" min="30" max="150" value="90" oninput="onSlider('3',this.value)" onchange="sendServo('3',this.value)">
          <div class="slider-labels"><span>30°</span><span>90°</span><span>150°</span></div>
          <div class="row" style="margin-top:8px">
            <button class="subtle sm" onclick="adjServo('3',-5)">◀ -5°</button>
            <button class="sm" onclick="setServo('3',45)">45°</button>
            <button class="sm" onclick="setServo('3',90)">90°</button>
            <button class="sm" onclick="setServo('3',135)">135°</button>
            <button class="subtle sm" onclick="adjServo('3',5)">+5° ▶</button>
          </div>
        </div>

        <!-- CANAL 4: SERVO 5 (AUXILIAR 3) -->
        <div class="servo-box">
          <div class="servo-head">
            <span class="servo-title">Canal 4 · Servo 5 (Auxiliar 3)</span>
            <span id="ang-4" class="pill neutral">90°</span>
          </div>
          <input type="range" id="slider-4" min="30" max="150" value="90" oninput="onSlider('4',this.value)" onchange="sendServo('4',this.value)">
          <div class="slider-labels"><span>30°</span><span>90°</span><span>150°</span></div>
          <div class="row" style="margin-top:8px">
            <button class="subtle sm" onclick="adjServo('4',-5)">◀ -5°</button>
            <button class="sm" onclick="setServo('4',45)">45°</button>
            <button class="sm" onclick="setServo('4',90)">90°</button>
            <button class="sm" onclick="setServo('4',135)">135°</button>
            <button class="subtle sm" onclick="adjServo('4',5)">+5° ▶</button>
          </div>
        </div>

        <!-- CANAL 5: SERVO 6 (AUXILIAR 4) -->
        <div class="servo-box">
          <div class="servo-head">
            <span class="servo-title">Canal 5 · Servo 6 (Auxiliar 4)</span>
            <span id="ang-5" class="pill neutral">90°</span>
          </div>
          <input type="range" id="slider-5" min="30" max="150" value="90" oninput="onSlider('5',this.value)" onchange="sendServo('5',this.value)">
          <div class="slider-labels"><span>30°</span><span>90°</span><span>150°</span></div>
          <div class="row" style="margin-top:8px">
            <button class="subtle sm" onclick="adjServo('5',-5)">◀ -5°</button>
            <button class="sm" onclick="setServo('5',45)">45°</button>
            <button class="sm" onclick="setServo('5',90)">90°</button>
            <button class="sm" onclick="setServo('5',135)">135°</button>
            <button class="subtle sm" onclick="adjServo('5',5)">+5° ▶</button>
          </div>
        </div>
      </div>
    </div>

    <!-- SECCIÓN 2: PUERTOS RESTANTES DISTRIBUIDOS (CH 6 A 15) -->
    <div class="card">
      <h2>Puertos de Expansión Disponibles (Canales 6 al 15)</h2>
      <p class="small">Distribución de los 10 puertos PWM restantes del PCA9685. Conecta en ellos microservos SG90 adicionales, brazos mecánicos o actuadores secundarios:</p>

      <div class="grid-exp">
        <!-- CANALES 6 AL 15 GENERADOS MODULARMENTE -->
        <div class="servo-box">
          <div class="servo-head"><span class="servo-title">Puerto CH 6</span><span id="ang-6" class="pill neutral">90°</span></div>
          <input type="range" id="slider-6" min="30" max="150" value="90" oninput="onSlider('6',this.value)" onchange="sendServo('6',this.value)">
          <div class="row"><button class="sm" onclick="setServo('6',45)">45°</button><button class="sm" onclick="setServo('6',90)">90°</button><button class="sm" onclick="setServo('6',135)">135°</button></div>
        </div>
        <div class="servo-box">
          <div class="servo-head"><span class="servo-title">Puerto CH 7</span><span id="ang-7" class="pill neutral">90°</span></div>
          <input type="range" id="slider-7" min="30" max="150" value="90" oninput="onSlider('7',this.value)" onchange="sendServo('7',this.value)">
          <div class="row"><button class="sm" onclick="setServo('7',45)">45°</button><button class="sm" onclick="setServo('7',90)">90°</button><button class="sm" onclick="setServo('7',135)">135°</button></div>
        </div>
        <div class="servo-box">
          <div class="servo-head"><span class="servo-title">Puerto CH 8</span><span id="ang-8" class="pill neutral">90°</span></div>
          <input type="range" id="slider-8" min="30" max="150" value="90" oninput="onSlider('8',this.value)" onchange="sendServo('8',this.value)">
          <div class="row"><button class="sm" onclick="setServo('8',45)">45°</button><button class="sm" onclick="setServo('8',90)">90°</button><button class="sm" onclick="setServo('8',135)">135°</button></div>
        </div>
        <div class="servo-box">
          <div class="servo-head"><span class="servo-title">Puerto CH 9</span><span id="ang-9" class="pill neutral">90°</span></div>
          <input type="range" id="slider-9" min="30" max="150" value="90" oninput="onSlider('9',this.value)" onchange="sendServo('9',this.value)">
          <div class="row"><button class="sm" onclick="setServo('9',45)">45°</button><button class="sm" onclick="setServo('9',90)">90°</button><button class="sm" onclick="setServo('9',135)">135°</button></div>
        </div>
        <div class="servo-box">
          <div class="servo-head"><span class="servo-title">Puerto CH 10</span><span id="ang-10" class="pill neutral">90°</span></div>
          <input type="range" id="slider-10" min="30" max="150" value="90" oninput="onSlider('10',this.value)" onchange="sendServo('10',this.value)">
          <div class="row"><button class="sm" onclick="setServo('10',45)">45°</button><button class="sm" onclick="setServo('10',90)">90°</button><button class="sm" onclick="setServo('10',135)">135°</button></div>
        </div>
        <div class="servo-box">
          <div class="servo-head"><span class="servo-title">Puerto CH 11</span><span id="ang-11" class="pill neutral">90°</span></div>
          <input type="range" id="slider-11" min="30" max="150" value="90" oninput="onSlider('11',this.value)" onchange="sendServo('11',this.value)">
          <div class="row"><button class="sm" onclick="setServo('11',45)">45°</button><button class="sm" onclick="setServo('11',90)">90°</button><button class="sm" onclick="setServo('11',135)">135°</button></div>
        </div>
        <div class="servo-box">
          <div class="servo-head"><span class="servo-title">Puerto CH 12</span><span id="ang-12" class="pill neutral">90°</span></div>
          <input type="range" id="slider-12" min="30" max="150" value="90" oninput="onSlider('12',this.value)" onchange="sendServo('12',this.value)">
          <div class="row"><button class="sm" onclick="setServo('12',45)">45°</button><button class="sm" onclick="setServo('12',90)">90°</button><button class="sm" onclick="setServo('12',135)">135°</button></div>
        </div>
        <div class="servo-box">
          <div class="servo-head"><span class="servo-title">Puerto CH 13</span><span id="ang-13" class="pill neutral">90°</span></div>
          <input type="range" id="slider-13" min="30" max="150" value="90" oninput="onSlider('13',this.value)" onchange="sendServo('13',this.value)">
          <div class="row"><button class="sm" onclick="setServo('13',45)">45°</button><button class="sm" onclick="setServo('13',90)">90°</button><button class="sm" onclick="setServo('13',135)">135°</button></div>
        </div>
        <div class="servo-box">
          <div class="servo-head"><span class="servo-title">Puerto CH 14</span><span id="ang-14" class="pill neutral">90°</span></div>
          <input type="range" id="slider-14" min="30" max="150" value="90" oninput="onSlider('14',this.value)" onchange="sendServo('14',this.value)">
          <div class="row"><button class="sm" onclick="setServo('14',45)">45°</button><button class="sm" onclick="setServo('14',90)">90°</button><button class="sm" onclick="setServo('14',135)">135°</button></div>
        </div>
        <div class="servo-box">
          <div class="servo-head"><span class="servo-title">Puerto CH 15</span><span id="ang-15" class="pill neutral">90°</span></div>
          <input type="range" id="slider-15" min="30" max="150" value="90" oninput="onSlider('15',this.value)" onchange="sendServo('15',this.value)">
          <div class="row"><button class="sm" onclick="setServo('15',45)">45°</button><button class="sm" onclick="setServo('15',90)">90°</button><button class="sm" onclick="setServo('15',135)">135°</button></div>
        </div>
      </div>
    </div>
  </div>

  <!-- BARRA DE ESTADO INFERIOR -->
  <div class="status-bar">
    <span id="act">Último comando: ninguno</span>
    <span id="act-ack" style="color:#38bdf8">ACK: Listo</span>
  </div>
</div>

<script>
const $=id=>document.getElementById(id);
const angles=new Array(16).fill(90);
let debounceTimer=null;

function switchTab(t){
  $('tab-diag').className='tab-content'+(t==='diag'?' active':'');
  $('tab-servos').className='tab-content'+(t==='servos'?' active':'');
  $('btn-tab-diag').className='tab-btn'+(t==='diag'?' active':'');
  $('btn-tab-servos').className='tab-btn'+(t==='servos'?' active':'');
}

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
    $('act').textContent='Comando: '+c;
    $('act-ack').textContent='ACK: '+(j.ok?(j.ack||'OK'):'ERROR');
    if(c.startsWith('S_ALL:')){
      const a=parseInt(c.substring(6));
      if(!isNaN(a)){
        for(let i=0;i<16;i++){
          angles[i]=a;
          const s=$('slider-'+i);const v=$('ang-'+i);
          if(s)s.value=a;
          if(v)v.textContent=a+'°';
        }
      }
    }
  }catch(e){
    $('act').textContent='Error al enviar: '+e;
    $('act-ack').textContent='ACK: FALLO';
  }
}

function onSlider(ch,val){
  const el=$('ang-'+ch);
  if(el)el.textContent=val+'°';
  angles[parseInt(ch)]=parseInt(val);
  clearTimeout(debounceTimer);
  debounceTimer=setTimeout(()=>{
    sendServo(ch,val);
  },70);
}

function sendServo(ch,val){
  cmd('S'+ch+':'+val);
}

function setServo(ch,val){
  const s=$('slider-'+ch);
  const el=$('ang-'+ch);
  if(s)s.value=val;
  if(el)el.textContent=val+'°';
  angles[parseInt(ch)]=parseInt(val);
  sendServo(ch,val);
}

function adjServo(ch,delta){
  const idx=parseInt(ch);
  let v=angles[idx]+delta;
  if(v<30)v=30;if(v>150)v=150;
  setServo(ch,v);
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
    if(d.pca)add(w,'PCA9685 activo. Recuerde alimentar el borne verde V+/GND a 5.0 V externos para mover los servos.');
    if(d.lcd)add(w,'LCD activa. Si no visualiza caracteres, ajuste el potenciómetro azul de contraste del backpack.');
    if(d.serialErrors)add(w,'Arduino reporta '+d.serialErrors+' errores en comandos serie recibidos.');
    if(d.lm&&d.dht&&d.lcd&&d.pca)add(w,'Todos los módulos de hardware reportan respuesta lógica correcta.');
  }catch(e){
    $('uart').className='pill bad';$('uart').textContent='WEB DESCONECTADA';
    $('warnings').textContent='El dispositivo móvil no puede comunicarse con el ESP32. Verifique la conexión Wi-Fi.';
  }
}
refresh();setInterval(refresh,1500);
</script></body></html>
)HTML";
