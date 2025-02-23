import os
import shutil
import time
import json
import pickle
from typing import Dict

import numpy as np

import torch

from .metrics import ANETdetection


def load_results_from_pkl(filename):
    assert os.path.isfile(filename)
    with open(filename, "rb") as f:
        results = pickle.load(f)
    return results

def load_results_from_json(filename):
    assert os.path.isfile(filename)
    with open(filename, "r") as f:
        results = json.load(f)
    if 'results' in results:
        results = results['results']
    return results

def results_to_dict(results):
    vidxs = sorted(list(set(results['video-id'])))
    results_dict = {}
    for vidx in vidxs:
        results_dict[vidx] = []

    for vidx, start, end, label, score in zip(
        results['video-id'],
        results['t-start'],
        results['t-end'],
        results['label'],
        results['score']
    ):
        results_dict[vidx].append(
            {
                "label" : int(label),
                "score" : float(score),
                "segment": [float(start), float(end)],
            }
        )
    return results_dict


def results_to_array(results, num_pred):
    vidxs = sorted(list(set(results['video-id'])))
    results_dict = {}
    for vidx in vidxs:
        results_dict[vidx] = {
            'label'   : [],
            'score'   : [],
            'segment' : [],
        }

    for vidx, start, end, label, score in zip(
        results['video-id'],
        results['t-start'],
        results['t-end'],
        results['label'],
        results['score']
    ):
        results_dict[vidx]['label'].append(int(label))
        results_dict[vidx]['score'].append(float(score))
        results_dict[vidx]['segment'].append(
            [float(start), float(end)]
        )

    for vidx in vidxs:
        label = np.asarray(results_dict[vidx]['label'])
        score = np.asarray(results_dict[vidx]['score'])
        segment = np.asarray(results_dict[vidx]['segment'])

        inds = np.argsort(score)[::-1][:num_pred]
        label, score, segment = label[inds], score[inds], segment[inds]
        results_dict[vidx]['label'] = label
        results_dict[vidx]['score'] = score
        results_dict[vidx]['segment'] = segment

    return results_dict


def postprocess_results(results, cls_score_file, num_pred=200, topk=2):
    if isinstance(results, str):
        results = load_results_from_pkl(results)
    results = results_to_array(results, num_pred)

    if '.json' in cls_score_file:
        cls_scores = load_results_from_json(cls_score_file)
    else:
        cls_scores = load_results_from_pkl(cls_score_file)

    processed_results = {
        'video-id': [],
        't-start' : [],
        't-end': [],
        'label': [],
        'score': []
    }

    for vid, result in results.items():
        curr_cls_scores = np.asarray(cls_scores[vid])
        topk_cls_idx = np.argsort(curr_cls_scores)[::-1][:topk]
        topk_cls_score = curr_cls_scores[topk_cls_idx]

        pred_score, pred_segment, pred_label = \
            result['score'], result['segment'], result['label']
        num_segs = min(num_pred, len(pred_score))

        new_pred_score = np.sqrt(topk_cls_score[:, None] @ pred_score[None, :]).flatten()
        new_pred_segment = np.tile(pred_segment, (topk, 1))
        new_pred_label = np.tile(topk_cls_idx[:, None], (1, num_segs)).flatten()

        processed_results['video-id'].extend([vid]*num_segs*topk)
        processed_results['t-start'].append(new_pred_segment[:, 0])
        processed_results['t-end'].append(new_pred_segment[:, 1])
        processed_results['label'].append(new_pred_label)
        processed_results['score'].append(new_pred_score)

    processed_results['t-start'] = np.concatenate(
        processed_results['t-start'], axis=0)
    processed_results['t-end'] = np.concatenate(
        processed_results['t-end'], axis=0)
    processed_results['label'] = np.concatenate(
        processed_results['label'],axis=0)
    processed_results['score'] = np.concatenate(
        processed_results['score'], axis=0)

    return processed_results
