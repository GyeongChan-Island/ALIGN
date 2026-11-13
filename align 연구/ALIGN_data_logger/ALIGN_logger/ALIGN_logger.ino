#include <Arduino.h>
#include <Wire.h>
#include <esp_timer.h>

// ESP32-WROOM-32; SDA=21, SCL=22. No third-party sensor library.
const uint8_t ADDR[2] = {0x68, 0x69};
const int64_t PERIOD_US = 20000;
bool running = false;
uint64_t seq = 0;
int64_t due = 0;

bool regWrite(uint8_t a, uint8_t r, uint8_t v) {
  Wire.beginTransmission(a); Wire.write(r); Wire.write(v);
  return Wire.endTransmission() == 0;
}
bool regRead(uint8_t a, uint8_t r, uint8_t *b, uint8_t n) {
  Wire.beginTransmission(a); Wire.write(r);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(a, n) != n) return false;
  for (int i=0; i<n; ++i) b[i] = Wire.read();
  return true;
}
bool initSensor(uint8_t a) {
  // Follow the user's working initialization: wake without device reset.
  if (!regWrite(a, 0x6B, 0x00)) {
    Serial.printf("#INIT_FAIL,0x%02X,wake write\n",a);
    return false;
  }
  delay(100);
  // DLPF=3 (~42/44Hz), internal 1kHz / (19+1) = 50Hz.
  if (!regWrite(a, 0x6C, 0) || !regWrite(a, 0x1A, 3) ||
      !regWrite(a, 0x19, 19) || !regWrite(a, 0x1B, 0) ||
      !regWrite(a, 0x1C, 0)) {
    Serial.printf("#INIT_FAIL,0x%02X,configuration write\n",a);
    return false;
  }
  uint8_t id=0;
  if (!regRead(a,0x75,&id,1)) {
    Serial.printf("#INIT_FAIL,0x%02X,ID read\n",a);
    return false;
  }
  Serial.printf("#ID,0x%02X,WHO_AM_I=0x%02X\n",a,id);
  if (id != 0x68) {
    Serial.printf("#WARN,0x%02X,unexpected ID; verify sensor model and scale before training\n",a);
  }
  const uint8_t regs[] = {0x6B,0x6C,0x1A,0x19,0x1B,0x1C};
  const uint8_t vals[] = {0,0,3,19,0,0};
  for (int i=0;i<6;++i) {
    uint8_t v;
    if (!regRead(a,regs[i],&v,1)) {
      Serial.printf("#INIT_FAIL,0x%02X,reg=0x%02X,read failed\n",a,regs[i]);
      return false;
    }
    if (v != vals[i]) {
      Serial.printf("#INIT_FAIL,0x%02X,reg=0x%02X,expected=0x%02X,actual=0x%02X\n",a,regs[i],vals[i],v);
      return false;
    }
  }
  return true;
}
bool readSensor(uint8_t a, float *v) {
  uint8_t b[14];
  if (!regRead(a, 0x3B, b, 14)) return false;
  const int offsets[] = {0,2,4,8,10,12};
  for (int i=0;i<6;++i) {
    int j=offsets[i];
    int16_t raw = (int16_t)(((uint16_t)b[j]<<8) | b[j+1]);
    v[i] = raw / (i<3 ? 16384.0f : 131.0f);
  }
  return true;
}
void setup() {
  Serial.begin(115200);
  Wire.begin(21,22,400000); Wire.setTimeOut(50);
  delay(1000);
  bool a=initSensor(ADDR[0]), b=initSensor(ADDR[1]);
  Serial.printf("#INIT,0x68=%s,0x69=%s\n",a?"OK":"FAIL",b?"OK":"FAIL");
  if (!a || !b) {
    while (true) { Serial.println("#FATAL,check power/wiring/AD0 then reset"); delay(2000); }
  }
  Serial.println("#READY,send S to start; X to stop");
}
void loop() {
  while (Serial.available()) {
    char c=Serial.read();
    if (c=='X') { running=false; Serial.println("#STOP"); }
    if (c=='S') {
      running=true; seq=0; due=esp_timer_get_time()+PERIOD_US;
      Serial.println("#START,50Hz,g,deg/s");
      Serial.println("seq,time_us,imu1_ax_g,imu1_ay_g,imu1_az_g,imu1_gx_dps,imu1_gy_dps,imu1_gz_dps,imu2_ax_g,imu2_ay_g,imu2_az_g,imu2_gx_dps,imu2_gy_dps,imu2_gz_dps");
    }
  }
  if (!running) { delay(1); return; }
  int64_t now=esp_timer_get_time();
  if (now<due) { delay(1); return; }
  // Skip overdue slots rather than emitting a burst of stale samples.
  uint64_t skipped=(now-due)/PERIOD_US;
  seq+=skipped; due+=(skipped+1)*PERIOD_US;
  uint64_t t=esp_timer_get_time(); // start of sequential two-sensor read
  float v[12];
  bool a=readSensor(ADDR[0],v), b=readSensor(ADDR[1],v+6);
  if (a && b) {
    char line[320];
    int n=snprintf(line,sizeof(line),"%llu,%llu",(unsigned long long)seq,(unsigned long long)t);
    for(int i=0;i<12;++i) n+=snprintf(line+n,sizeof(line)-n,",%.5f",v[i]);
    Serial.println(line);
  } else Serial.printf("#READ_FAIL,%llu,imu1=%d,imu2=%d\n",(unsigned long long)seq,a,b);
  ++seq; // failures consume a slot too, so CSV gaps remain visible
}
