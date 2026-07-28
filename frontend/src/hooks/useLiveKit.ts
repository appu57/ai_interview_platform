// src/hooks/useLiveKit.ts
import { useEffect, useState } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';

export function useLiveKit(token: string, onEvent: (event: any) => void) {
  const [isConnected, setIsConnected] = useState(false);
  const [status, setStatus] = useState("Initializing...");

  useEffect(() => {
    if (!token) return;

    const room = new Room({ adaptiveStream: true, dynacast: true });

    async function startSession() {
      try {
        const url = "ws://localhost:7880";
        await room.connect(url, token);
        setIsConnected(true);
        
        // Turn on mic
        await room.localParticipant.setMicrophoneEnabled(true);

        // Catch backend agent voice track
        room.on(RoomEvent.TrackSubscribed, (track) => {
          if (track.kind === Track.Kind.Audio) {
            const el = track.attach();
            document.body.appendChild(el);
          }
        });

        // Catch data events (tutor_hint, state_update)
        room.on(RoomEvent.DataReceived, (payload, participant, kind, topic) => {
          if (topic === "agent_events") {
            const data = JSON.parse(new TextDecoder().decode(payload));
            onEvent(data);
          }
        });

      } catch (err) {
        console.error("WebRTC Connection failed", err);
        setStatus("Connection Error");
      }
    }

    startSession();
    return () => { room.disconnect(); };
  }, [token]);

  return { isConnected, status };
}