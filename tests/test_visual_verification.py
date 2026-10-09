import json
import unittest
import httpx
from agent.visual_verification import VerifiedSocialVisionInvoker
from agent.vision_policy import VisionDecisionAgent

class VisualVerificationTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, outputs):
        calls=[]
        def handler(request):
            payload=json.loads(request.content);calls.append(payload)
            return httpx.Response(200,json={'request_id':payload['request_id'],'output':outputs[len(calls)-1]})
        invoker=VerifiedSocialVisionInvoker(transport=httpx.MockTransport(handler))
        try:
            raw=await invoker.ainvoke([b'jpeg'],'Task and complete catalog')
            return VisionDecisionAgent._parse_output(raw),calls,invoker.last_metrics
        finally:await invoker.close()

    async def test_other_person_greeting_is_not_executed(self):
        d,c,m=await self.invoke(['{"action":"execute_skill","skill":"handshake"}','OTHER'])
        self.assertEqual(d.action,'ignore')
        self.assertEqual(len(c),2)
        self.assertIn('handshake',m['decision_raw'])
        self.assertEqual(c[0]['frames'],c[1]['frames'])

    async def test_verified_gesture_preserves_parameters(self):
        d,c,m=await self.invoke(['{"action":"execute_skill","skill":"wave","arguments":{"arm":"left"}}','CAMERA'])
        self.assertEqual(d.arguments,{'arm':'left'})
        self.assertEqual(d.skill,'wave')

    async def test_uncertain_or_malformed_recipient_does_not_authorize_action(self):
        for output in ['NONE','uncertain','CAMERA or OTHER','{"recipient":"CAMERA"}']:
            with self.subTest(output=output):
                d,_,_=await self.invoke(['{"action":"execute_skill","skill":"high_five"}',output])
                self.assertEqual(d.action,'ignore')

    async def test_other_tools_and_idle_do_not_need_social_confirmation(self):
        for output in ['{"action":"ignore"}','{"action":"execute_skill","skill":"set_speed_mode","arguments":{"mode":1}}']:
            d,c,_=await self.invoke([output])
            self.assertEqual(len(c),1)
            self.assertEqual(d.action,json.loads(output)['action'])

    async def test_truncated_actions_are_rejected(self):
        with self.assertRaises(Exception):
            await self.invoke(['{"action":"execute_skill","skill":"wave"'])
